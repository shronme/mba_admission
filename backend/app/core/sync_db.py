"""
Synchronous SQLAlchemy engine/session.

The FastAPI app uses async SQLAlchemy (`app.core.db`) for request handling, but
some background jobs (and compatibility helpers) still use a synchronous session
via `settings.database_url_sync()`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_sync_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_sync_engine():
    global _sync_engine, _SessionLocal
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.database_url_sync(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        _SessionLocal = sessionmaker(
            bind=_sync_engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _sync_engine


def get_sync_session_factory() -> sessionmaker[Session]:
    get_sync_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def sync_session_scope() -> Iterator[Session]:
    """Commit on success, rollback on error, always close."""

    SessionLocal = get_sync_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
