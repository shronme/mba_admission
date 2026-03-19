from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


def create_engine() -> AsyncEngine:
    """
    Create the shared async SQLAlchemy engine.

    Note: we don't attempt schema initialization here (Task 001).
    """

    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )


engine: AsyncEngine = create_engine()
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def async_select_one() -> int:
    """A minimal DB connectivity check (`SELECT 1`)."""

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        value = int(result.scalar_one())
        logger.info("Postgres connectivity check returned %s", value)
        return value


async def test_db_connection() -> dict:
    """Manual DB check helper (not called automatically in health)."""

    try:
        value = await async_select_one()
        return {"db_connected": True, "select_one": value}
    except Exception as e:  # noqa: BLE001 - diagnostics helper
        return {"db_connected": False, "error": str(e)}

