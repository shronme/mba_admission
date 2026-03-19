from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Environment-driven configuration.

    Defaults are provided so local imports (and CI `/health`) work even
    without Postgres/Redis running.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = Field(default="development", validation_alias="ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # Example defaults work with local docker-compose.
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    # FastAPI health checks
    healthcheck_db: bool = Field(default=False, validation_alias="HEALTHCHECK_DB")
    healthcheck_redis: bool = Field(default=False, validation_alias="HEALTHCHECK_REDIS")

    # Celery
    celery_task_default_queue: str = Field(
        default="default", validation_alias="CELERY_TASK_DEFAULT_QUEUE"
    )

    # Browser clients (Next.js dev server, deployed web app). Comma-separated origins.
    cors_origins: str = Field(
        default=(
            "http://localhost:3000,"
            "http://127.0.0.1:3000,"
            "http://[::1]:3000"
        ),
        validation_alias="CORS_ORIGINS",
    )

    def cors_origin_list(self) -> list[str]:
        parts = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # Empty env (e.g. CORS_ORIGINS=) would skip middleware and break browser fetches.
        if parts:
            return parts
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://[::1]:3000",
        ]

    def celery_broker_url(self) -> str:
        return self.redis_url

    def celery_result_backend(self) -> str:
        return self.redis_url


settings = Settings()

