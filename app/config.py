from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    整个文档处理平台的配置。
    """

    # ========================================================
    # Application
    # ========================================================

    app_name: str = "Async Document Platform"

    app_env: str = "development"

    debug: bool = False

    log_level: str = "INFO"

    # ========================================================
    # PostgreSQL
    # ========================================================

    database_url: str = (
        "postgresql+asyncpg://docuser:docpass@localhost:5432/docplatform"
    )

    # ========================================================
    # Redis
    # ========================================================

    redis_host: str = "localhost"

    redis_port: int = 6379

    redis_db: int = 0

    # ========================================================
    # Storage
    # ========================================================

    storage_root: str = "./data"

    # 最大上传 20 MB
    max_upload_bytes: int = 20 * 1024 * 1024

    # ========================================================
    # Job
    # ========================================================

    # Redis中的Job状态保存24小时
    job_state_ttl_seconds: int = 24 * 60 * 60

    worker_max_jobs: int = 4

    job_timeout_seconds: int = 180

    max_job_tries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property  # 只读属性， 拼接目录
    def uploads_dir(self) -> Path:
        return Path(self.storage_root) / "uploads"

    @property
    def results_dir(self) -> Path:
        return Path(self.storage_root) / "results"


@lru_cache
def get_settings() -> Settings:
    return Settings()
