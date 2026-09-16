from typing import Annotated, Optional
from uuid import uuid4

from arq.connections import ArqRedis
from arq.jobs import Job
from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.config import (
    Settings,
    get_settings,
)
from app.database import get_db
from app.models import Document
from app.redis_client import (
    get_arq_redis,
    get_state_redis,
)
from app.task_state import (
    ACTIVE_JOB_STATUSES,
    RETRYABLE_JOB_STATUSES,
    get_job_state,
    set_job_state,
    state_to_dict,
)


class DocumentNotFoundError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


class InvalidJobStateError(Exception):
    pass


class JobService:
    def __init__(
        self,
        db: AsyncSession,
        arq_redis: ArqRedis,
        state_redis: Redis,
        settings: Settings,
    ) -> None:

        self.db = db

        self.arq = arq_redis

        self.state = state_redis

        self.settings = settings

    async def _get_document(
        self,
        document_id: str,
    ) -> Document:

        document = await self.db.get(
            Document,
            document_id,
        )

        if document is None:
            raise DocumentNotFoundError(document_id)

        return document

    async def create_parse_job(
        self,
        document_id: str,
        *,
        retry_of: Optional[str] = None,
    ) -> dict:  # 创建文档解析任务，提交到 arq 队列

        document = await self._get_document(document_id)

        # 普通创建任务时，
        # 不允许已有活跃任务
        if retry_of is None and document.last_job_id:
            current = await get_job_state(
                self.state,
                document.last_job_id,
            )

            if current and current.get("status") in ACTIVE_JOB_STATUSES:
                raise InvalidJobStateError("Document already has an active job")

        job_id = uuid4().hex

        fields = {
            # 不能有job_id了，不然会和set_job_state中产生冲突
            "document_id": (document_id),
            "status": "queued",
            "progress": "0",
            "message": ("Waiting for worker"),
            "attempt": "0",
            "max_attempts": str(self.settings.max_job_tries),
            "cancel_requested": "0",
            "error": "",
        }

        if retry_of:
            fields["retry_of"] = retry_of
        # 更新数据库状态
        await set_job_state(
            self.state,
            job_id,
            (self.settings.job_state_ttl_seconds),
            **fields,
        )

        # 更新文档状态和最后任务ID

        document.parse_status = "queued"

        document.last_job_id = job_id

        # 更新数据库
        await self.db.commit()

        job = await self.arq.enqueue_job(
            "parse_document_job",  # worker中定义的任务函数名
            job_id,
            document_id,  # 对应的 worker 那边定义的任务函数
            _job_id=job_id,  # 指定arq的job_id和业务job_id保持一致
        )

        if job is None:
            document.parse_status = "failed"

            await self.db.commit()

            await set_job_state(
                self.state,
                job_id,
                (self.settings.job_state_ttl_seconds),
                status="failed",
                error=("Failed to enqueue job"),
            )

            raise RuntimeError("Failed to enqueue job")

        state = await get_job_state(
            self.state,
            job_id,
        )

        return state_to_dict(state, job_id)  # pyright: ignore[reportArgumentType]

    async def get_job(
        self,
        job_id: str,
    ) -> dict:

        state = await get_job_state(
            self.state,
            job_id,
        )

        if state is None:
            raise JobNotFoundError(job_id)

        return state_to_dict(state, job_id)

    async def cancel_job(
        self,
        job_id: str,
    ) -> dict:
        """
        取消采用双保险：

        1. Redis设置cancel_requested
        2. 尝试Arq Job.abort()

        即使abort没有立即成功，
        Worker后续也会检查Redis取消标志。
        """

        state = await get_job_state(
            self.state,
            job_id,
        )

        if state is None:
            raise JobNotFoundError(job_id)

        status = state.get("status")

        if status in {
            "completed",
            "failed",
            "cancelled",
        }:
            raise InvalidJobStateError(f"Cannot cancel job in state {status}")

        await set_job_state(
            self.state,
            job_id,
            (self.settings.job_state_ttl_seconds),
            status="cancel_requested",
            cancel_requested="1",
            message=("Cancellation requested"),
        )  # **业务 Redis 标记**：设置`cancel_requested="1"`，status 改为`cancel_requested`

        # Arq官方取消机制。
        #
        # 不把它作为唯一取消机制，
        # 因为我们自己的Redis flag
        # 更容易让业务状态保持一致。
        arq_job = Job(
            job_id=job_id,
            redis=self.arq,
        )  # `arq.jobs.Job` 是 arq 的**任务操作对象**，根据已知的`job_id`，重新在代码里拼装出一个任务对象，不需要重新入队。
        # 前面`enqueue_job(..., _job_id=job_id)`，就是让 arq 内部任务 ID = 业务 job_id，所以这里可以直接拿这个 id 构造 Job

        try:
            await arq_job.abort(
                timeout=0.2,
                poll_delay=0.05,
            )  # 尝试终止 arq 队列任务

        except TimeoutError:
            # Worker之后仍会检查
            # cancel_requested。
            pass

        document_id = state["document_id"]

        document = await self.db.get(
            Document,
            document_id,
        )
        # 更新文档状态为取消中
        if document is not None:
            document.parse_status = "cancel_requested"

            await self.db.commit()

        new_state = await get_job_state(
            self.state,
            job_id,
        )

        return state_to_dict(new_state, job_id)  # type: ignore

    async def retry_job(
        self,
        job_id: str,
    ) -> dict:

        state = await get_job_state(
            self.state,
            job_id,
        )

        if state is None:
            raise JobNotFoundError(job_id)

        if state.get("status") not in RETRYABLE_JOB_STATUSES:
            raise InvalidJobStateError("Only failed or cancelled jobs can be retried")

        document_id = state["document_id"]

        # 创建一个新的Job ID。
        return await self.create_parse_job(
            document_id,
            retry_of=job_id,
        )


async def get_job_service(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    arq_redis: Annotated[
        ArqRedis,
        Depends(get_arq_redis),
    ],
    state_redis: Annotated[
        Redis,
        Depends(get_state_redis),
    ],
    settings: Annotated[
        Settings,
        Depends(get_settings),
    ],
) -> JobService:

    return JobService(
        db=db,
        arq_redis=arq_redis,
        state_redis=state_redis,
        settings=settings,
    )
