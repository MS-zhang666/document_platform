from contextlib import (
    asynccontextmanager,
)

from arq.connections import (
    ArqRedis,
)
from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import (
    get_settings,
)
from app.database import (
    engine,
    init_db,
)
from app.logging_config import (
    configure_logging,
)
from app.redis_client import (
    create_arq_redis,
    create_state_redis,
)
from app.routers import (
    documents,
    health,
    jobs,
)
from app.storage import (
    ensure_storage_dirs,
)

settings = get_settings()


configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):

    # ========================================================
    # Storage
    # ========================================================

    ensure_storage_dirs(settings)

    # ========================================================
    # PostgreSQL
    # ========================================================

    await init_db()

    # ========================================================
    # Redis
    # ========================================================

    state_redis: Redis = create_state_redis(settings)

    arq_redis: ArqRedis = await create_arq_redis(settings)

    await state_redis.ping()

    await arq_redis.ping()

    app.state.state_redis = state_redis

    app.state.arq_redis = arq_redis

    yield

    await state_redis.aclose()

    await arq_redis.aclose()

    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)


app.include_router(health.router)

app.include_router(documents.router)

app.include_router(jobs.router)
