from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
)
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.database import get_db
from app.redis_client import (
    get_state_redis,
)
from app.schemas import (
    HealthResponse,
    ReadyResponse,
)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
)
async def health():

    return {
        "status": "ok",
    }


@router.get(
    "/ready",
    response_model=ReadyResponse,
)
async def ready(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    redis: Annotated[
        Redis,
        Depends(
            get_state_redis
        ),  # `redis.asyncio.Redis`：异步客户端，所有操作（`ping` / `hget` / `hset`）都要加 `await`
    ],
):

    await db.execute(text("SELECT 1"))

    await redis.ping()

    return {
        "status": "ready",
        "postgres": "ok",
        "redis": "ok",
    }
