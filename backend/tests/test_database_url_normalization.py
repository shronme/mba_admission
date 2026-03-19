"""DATABASE_URL normalization for asyncpg (Railway-style URLs)."""

from app.core.config import Settings


def test_normalize_postgres_scheme(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")
    s = Settings()
    assert s.database_url == "postgresql+asyncpg://u:p@h:5432/db"


def test_normalize_postgresql_scheme(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    s = Settings()
    assert s.database_url == "postgresql+asyncpg://u:p@h:5432/db"


def test_preserves_existing_asyncpg(monkeypatch) -> None:
    url = "postgresql+asyncpg://u:p@h:5432/db"
    monkeypatch.setenv("DATABASE_URL", url)
    s = Settings()
    assert s.database_url == url


def test_database_url_sync_for_alembic(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    s = Settings()
    assert s.database_url_sync() == "postgresql+psycopg://u:p@h:5432/db"
