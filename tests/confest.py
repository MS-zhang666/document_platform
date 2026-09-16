import os

import pytest
from fastapi.testclient import (
    TestClient,
)
from redis import Redis

# 必须在导入app之前设置。
os.environ.setdefault(
    "APP_ENV",
    "test",
)

os.environ.setdefault(
    "DATABASE_URL",
    ("sqlite+aiosqlite:///./test.db"),
)

os.environ.setdefault(
    "REDIS_HOST",
    "localhost",
)

os.environ.setdefault(
    "REDIS_PORT",
    "6379",
)

# 使用独立Redis DB
os.environ.setdefault(
    "REDIS_DB",
    "15",
)

os.environ.setdefault(
    "STORAGE_ROOT",
    "./.test-data",
)


from app.main import app  # noqa: E402


@pytest.fixture(
    scope="session",
    autouse=True,
)
def clean_redis():

    redis = Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.environ["REDIS_PORT"]),
        db=int(os.environ["REDIS_DB"]),
    )

    redis.flushdb()

    yield

    redis.flushdb()

    redis.close()


@pytest.fixture(scope="session")
def client():

    with TestClient(app) as test_client:
        yield test_client
