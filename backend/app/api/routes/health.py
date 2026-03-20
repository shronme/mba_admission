import logging

from fastapi import APIRouter
import redis

from app.core.config import settings
from app.core.db import test_db_connection

router = APIRouter(tags=["health"])

logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict:
    # Keep this lightweight for CI/local startup.
    payload: dict = {"status": "ok"}

    if settings.healthcheck_redis:
        try:
            redis.Redis.from_url(settings.redis_url).ping()
            payload["redis_connected"] = True
        except Exception as e:  # noqa: BLE001
            payload["redis_connected"] = False
            payload["redis_error"] = str(e)
            logger.warning("health_redis_failed error=%s", str(e))

    if settings.healthcheck_db:
        payload.update(await test_db_connection())
        if not payload.get("db_connected"):
            logger.warning("health_db_failed error=%s", payload.get("error"))

    return payload

