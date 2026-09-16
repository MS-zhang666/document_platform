import asyncio
import logging
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Optional

from app.config import (
    get_settings,
)
from app.database import (
    AsyncSessionLocal,
    init_db,
)
from app.models import Document
from app.parser import (
    ParseResult,
    parse_document_file,
)
from app.redis_client import (
    build_arq_redis_settings,
    create_state_redis,
)
from app.storage import (
    ensure_storage_dirs,
    write_result_text,
)
from app.task_state import (
    get_job_state,
    set_job_state,
)
from arq import Retry
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


settings = get_settings()


class UserCancelledError(Exception):
    pass


async def worker_startup(
    ctx,
) -> None:

    await init_db()

    ensure_storage_dirs(settings)

    state_redis = create_state_redis(settings)

    await state_redis.ping()

    ctx["state_redis"] = state_redis

    ctx["settings"] = settings


async def worker_shutdown(
    ctx,
) -> None:

    redis: Optional[Redis] = ctx.get("state_redis")

    if redis is not None:
        await redis.aclose()


async def cancel_requested(
    redis: Redis,
    job_id: str,
) -> bool:

    state = await get_job_state(
        redis,
        job_id,
    )

    if state is None:
        return False

    return (
        state.get("cancel_requested") == "1"
    )  # 协作式取消的检查点，代码中多处调用这个函数


async def mark_document_status(
    document_id: str,
    status: str,
) -> None:  # 单独打开数据库会话，**仅更新数据库 Document 的 parse_status**

    async with AsyncSessionLocal() as db:
        document = await db.get(
            Document,
            document_id,
        )

        if document is None:
            return

        document.parse_status = status

        await db.commit()


async def mark_cancelled(
    redis: Redis,
    job_id: str,
    document_id: str,
) -> None:

    await set_job_state(
        redis,
        job_id,
        (settings.job_state_ttl_seconds),
        status="cancelled",
        message="Job cancelled",
        cancel_requested="1",
    )

    await mark_document_status(
        document_id,
        "cancelled",
    )
    # 更新 Redis 任务状态为`cancelled` + 更新数据库 parse_status="cancelled"


async def mark_failed(
    redis: Redis,
    job_id: str,
    document_id: str,
    error: Exception,
) -> None:

    await set_job_state(
        redis,
        job_id,
        (settings.job_state_ttl_seconds),
        status="failed",
        message="Job failed",
        error=str(error)[:500],
    )

    await mark_document_status(
        document_id,
        "failed",
    )


async def parse_document_job(
    ctx,
    job_id: str,
    document_id: str,
) -> dict:

    redis: Redis = ctx[
        "state_redis"
    ]  # 取出在 worker 启动阶段预先存放的 state_redis 连接实例

    attempt = int(
        ctx.get("job_try") or 1
    )  # 取出当前任务的尝试次数，第一次执行为1，失败重试时会递增

    # ========================================================
    # 已经被用户取消
    # ========================================================

    if await cancel_requested(
        redis,
        job_id,
    ):  # 任务刚被做出来，在队列中执行前就检查是否已经被用户取消
        await mark_cancelled(
            redis,
            job_id,
            document_id,
        )

        return {
            "cancelled": True,
        }

    await set_job_state(
        redis,
        job_id,
        (settings.job_state_ttl_seconds),
        status="running",
        progress="5",
        message="Worker started",
        attempt=str(attempt),
    )

    # ========================================================
    # 获取Document元数据
    # ========================================================

    async with AsyncSessionLocal() as db:
        document = await db.get(
            Document,
            document_id,
        )

        if document is None:
            error = RuntimeError("Document not found")

            await mark_failed(
                redis,
                job_id,
                document_id,
                error,
            )

            raise error

        document.parse_status = "running"

        document.last_job_id = job_id

        await db.commit()

        input_path = Path(document.storage_path)  # 文件路径

        file_type = document.file_type  # 文件类型

    async def progress(
        percentage: int,
        message: str,
    ) -> None:  # 每个解析阶段都检查取消请求。内部回调函数

        # 每个解析阶段都检查取消请求。
        if await cancel_requested(
            redis,
            job_id,
        ):
            raise UserCancelledError()  # 协作式取消，抛出异常，交给外层捕获处理,因为后续的parse_document_file调用了该回调函数

        await set_job_state(
            redis,
            job_id,
            (settings.job_state_ttl_seconds),
            status="running",
            progress=str(percentage),
            message=message,
            attempt=str(attempt),
        )

    try:
        # ====================================================
        # 真正解析文件
        # ====================================================

        result: ParseResult = await parse_document_file(
            input_path,
            file_type,
            progress,
        )

        if await cancel_requested(
            redis,
            job_id,
        ):
            raise UserCancelledError()

        # ====================================================
        # 保存解析结果
        # ====================================================

        result_path = await write_result_text(
            document_id,
            result.text,
            settings,
        )

        # ====================================================
        # 更新PostgreSQL元数据
        # ====================================================

        async with AsyncSessionLocal() as db:
            document = await db.get(
                Document,
                document_id,
            )

            if document is None:
                raise RuntimeError("Document disappeared")

            document.result_path = str(result_path)

            document.page_count = result.page_count

            document.char_count = result.char_count

            document.parse_status = "completed"

            document.parsed_at = datetime.now(timezone.utc)

            await db.commit()

        message = "Job completed"

        if file_type == "pdf" and result.char_count == 0:
            message = "Completed, but no text was extracted. The PDF may be scanned."

        await set_job_state(
            redis,
            job_id,
            (settings.job_state_ttl_seconds),
            status="completed",
            progress="100",
            message=message,
            attempt=str(attempt),
            error="",
        )

        return {
            "job_id": job_id,
            "document_id": (document_id),
            "success": True,
        }

    # ========================================================
    # Cooperative Cancel
    # ========================================================

    except UserCancelledError:  # `progress()`回调检测到`cancel_requested="1"`手动抛出
        await mark_cancelled(
            redis,
            job_id,
            document_id,
        )

        return {
            "cancelled": True,
        }

    # ========================================================
    # Arq abort / Worker shutdown
    # ========================================================

    except (
        asyncio.CancelledError
    ):  # `arq.jobs.Job.abort()` 或 Worker shutdown 导致的取消异常
        # 如果确实是用户请求取消，
        # 就作为正常Cancelled状态结束。
        if await cancel_requested(
            redis,
            job_id,
        ):
            await mark_cancelled(
                redis,
                job_id,
                document_id,
            )

            return {
                "cancelled": True,
            }

        # 否则可能是Worker shutdown。
        # 继续抛出，让Arq按自身机制处理。
        raise

    # ========================================================
    # 临时I/O错误 → 自动重试
    # ========================================================

    except OSError as exc:
        if attempt < settings.max_job_tries:
            await set_job_state(
                redis,
                job_id,
                (settings.job_state_ttl_seconds),
                status="retrying",
                message=("Temporary I/O error, retry scheduled"),
                attempt=str(attempt),  # Redis Hash 里面**所有值都只能存字符串**
                error=str(exc)[:500],  # 只保留字符串前 500 个字符，超出部分全部截断丢弃
            )

            await mark_document_status(
                document_id,
                "retrying",
            )

            # 抛出 arq 专属的 Retry 异常，告诉arq：过一段时间重新跑这个任务
            # 2秒、4秒……
            raise Retry(
                defer=min(
                    attempt * 2,
                    30,
                )
            ) from exc

        await mark_failed(
            redis,
            job_id,
            document_id,
            exc,
        )

        raise

    # ========================================================
    # 其他错误 → failed
    # ========================================================

    except Exception as exc:
        await mark_failed(
            redis,
            job_id,
            document_id,
            exc,
        )

        logger.exception("document_parse_failed")

        raise


class WorkerSettings:
    functions = [
        parse_document_job,
    ]

    redis_settings = build_arq_redis_settings(
        settings
    )  # 组装配置，但是没有建立redis连接池，连接池在worker启动时建立

    on_startup = worker_startup

    on_shutdown = worker_shutdown

    max_jobs = settings.worker_max_jobs

    job_timeout = settings.job_timeout_seconds

    max_tries = settings.max_job_tries

    keep_result = 3600

    # Job.abort()需要开启
    allow_abort_jobs = True

    # 方便Docker健康检查
    health_check_interval = 5
