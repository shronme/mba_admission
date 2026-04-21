from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_database() -> None:
    """
    Ensure the test database schema is at Alembic head before running tests.

    The test suite uses a real Postgres database (DATABASE_URL) and expects all
    tables/constraints to exist.
    """
    # Avoid surprising local runs where no DB is configured.
    if not os.getenv("DATABASE_URL"):
        return

    from alembic import command
    from alembic.config import Config

    from app.core.config import settings

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url_sync())
    command.upgrade(cfg, "head")

