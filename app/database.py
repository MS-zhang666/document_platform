from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings

settings = Settings()

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI数据库依赖。

    每个Request拥有自己的AsyncSession。
    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """
    第一个版本为了让项目直接跑通，
    自动创建数据库表。

    项目完成后建议改为Alembic迁移。
    """
    # 确保models.py中所有的表都被导入到Base.metadata中
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
