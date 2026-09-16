from datetime import (
    datetime,
    timezone,
)
from typing import Optional

from redis.asyncio import Redis

ACTIVE_JOB_STATUSES = {
    "queued",
    "running",
    "retrying",
    "cancel_requested",
}


RETRYABLE_JOB_STATUSES = {
    "failed",
    "cancelled",
    "cancel_requested",
}


def task_key(
    job_id: str,
) -> str:

    return f"task:{job_id}"  # 设置为Redis的key


def now_iso() -> str:

    return datetime.now(timezone.utc).isoformat()


# 写入任务状态，核心
async def set_job_state(
    redis: Redis,
    job_id: str,
    ttl_seconds: int,
    **fields,  # 解包操作
) -> None:

    mapping = {}

    for key, value in fields.items():
        if value is None:
            continue

        mapping[key] = str(value)

    mapping["updated_at"] = now_iso()

    await redis.hset(task_key(job_id), mapping=mapping)  # type: ignore

    await redis.expire(
        task_key(job_id),
        ttl_seconds,
    )


async def get_job_state(
    redis: Redis,
    job_id: str,
) -> Optional[dict[str, str]]:

    data = await redis.hgetall(task_key(job_id))  # type: ignore

    if not data:
        return None

    return data


async def delete_job_state(
    redis: Redis,
    job_id: str,
) -> None:

    await redis.delete(task_key(job_id))


# 类型转换层
def state_to_dict(
    state: dict[str, str],
    job_id: Optional[str],
) -> dict:

    return {
        "job_id": job_id,
        "document_id": state["document_id"],
        "status": state.get(
            "status",
            "unknown",
        ),
        "progress": int(
            state.get(
                "progress",
                "0",
            )
        ),
        "message": state.get(
            "message",
            "",
        ),
        "attempt": int(
            state.get(
                "attempt",
                "0",
            )
        ),
        "max_attempts": int(
            state.get(
                "max_attempts",
                "1",
            )
        ),
        "cancel_requested": (
            state.get(
                "cancel_requested",
                "0",
            )
            == "1"
        ),
        "error": (state.get("error") or None),
        "retry_of": (state.get("retry_of") or None),
    }
