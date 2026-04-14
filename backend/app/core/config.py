from pydantic import Field, field_validator
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

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url_for_asyncpg(cls, v: object) -> object:
        """
        Railway/Postgres often provide `postgres://` or `postgresql://` without a driver.
        SQLAlchemy then picks the **sync** dialect (psycopg2), which we do not install.
        Async SQLAlchemy must use the asyncpg driver: `postgresql+asyncpg://`.
        """
        if not isinstance(v, str):
            return v
        s = v.strip()
        if s.startswith("postgres://"):
            return "postgresql+asyncpg://" + s[len("postgres://") :]
        if s.startswith("postgresql://") and not s.startswith("postgresql+"):
            return "postgresql+asyncpg://" + s[len("postgresql://") :]
        return v

    # FastAPI health checks
    healthcheck_db: bool = Field(default=False, validation_alias="HEALTHCHECK_DB")

    # In-process job runner (Celery replacement)
    job_runner_enabled: bool = Field(default=True, validation_alias="JOB_RUNNER_ENABLED")
    job_runner_concurrency: int = Field(default=2, validation_alias="JOB_RUNNER_CONCURRENCY")
    job_runner_queue_maxsize: int = Field(
        default=200, validation_alias="JOB_RUNNER_QUEUE_MAXSIZE"
    )
    job_runner_stale_seconds: int = Field(
        default=15 * 60, validation_alias="JOB_RUNNER_STALE_SECONDS"
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

    def database_url_sync(self) -> str:
        """
        Synchronous SQLAlchemy URL for Alembic and other sync tools.

        The app runtime uses asyncpg (`postgresql+asyncpg://`); migrations use psycopg3.
        """

        u = self.database_url
        if u.startswith("postgresql+asyncpg://"):
            return "postgresql+psycopg://" + u[len("postgresql+asyncpg://") :]
        return u


settings = Settings()

