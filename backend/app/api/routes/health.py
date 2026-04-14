import logging

from fastapi import APIRouter

from app.core.config import settings
from app.core.db import test_db_connection

router = APIRouter(tags=["health"])

logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict:
    # Keep this lightweight for CI/local startup.
    payload: dict = {"status": "ok"}

    if settings.healthcheck_db:
        payload.update(await test_db_connection())
        if not payload.get("db_connected"):
            logger.warning("health_db_failed error=%s", payload.get("error"))

    return payload

