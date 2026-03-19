import asyncio
import logging

import redis
from celery import shared_task

from app.core.config import settings
from app.core.db import async_select_one

logger = logging.getLogger(__name__)


async def _wiring_smoke_async() -> dict:
    # Redis ping can be done synchronously (fast).
    redis_client = redis.Redis.from_url(settings.redis_url)
    redis_client.ping()

    select_one = await async_select_one()
    return {"redis_connected": True, "db_connected": True, "select_one": select_one}


@shared_task(name="app.workers.tasks.wiring_smoke_job")
def wiring_smoke_job() -> dict:
    """
    End-to-end wiring check payload for Task 001.

    Runs in Celery worker:
    - Redis connectivity test
    - Postgres `SELECT 1` connectivity test
    """

    try:
        return asyncio.run(_wiring_smoke_async())
    except Exception as e:  # noqa: BLE001 - surface failure for smoke test
        logger.exception("Wiring smoke job failed")
        return {"redis_connected": False, "db_connected": False, "error": str(e)}

