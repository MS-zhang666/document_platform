from typing import Annotated

from arq import create_pool
from arq.connections import (
    ArqRedis,
    RedisSettings,
)
from fastapi import Depends, Request
from redis.asyncio import Redis

from app.config import (
    Settings,
    get_settings,
)


def build_arq_redis_settings(
    settings: Settings,
) -> RedisSettings:

    return RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_db,
    )  # 项目全局 `Settings` 转换成 Arq 需要的 `RedisSettings`


def create_state_redis(
    settings: Settings,
) -> Redis:

    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
    )  # 创建**业务 redis 客户端实例**,**不连接 redis**，同步`def`


async def create_arq_redis(
    settings: Settings,
) -> ArqRedis:

    return await create_pool(
        build_arq_redis_settings(settings)
    )  # 创建Arq任务队列连接池create_pool() 内部会立刻连接 Redis，属于网络 IO，必须 async/await。


# 在 `lifespan`（main.py）建立与示例构建的关联
async def get_state_redis(
    request: Request,
) -> Redis:

    return request.app.state.state_redis


async def get_arq_redis(
    request: Request,
) -> ArqRedis:

    return request.app.state.arq_redis


# 简化路由声明
StateRedisDep = Annotated[
    Redis,
    Depends(get_state_redis),
]


ArqRedisDep = Annotated[
    ArqRedis,
    Depends(get_arq_redis),
]


SettingsDep = Annotated[
    Settings,
    Depends(get_settings),
]
