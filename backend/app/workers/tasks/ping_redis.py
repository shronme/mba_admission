import logging

import redis
from celery import shared_task

from app.core.config import settings

logger = logging.getLogger(__name__)


@shared_task(name="app.workers.tasks.ping_redis")
def ping_redis() -> dict:
    """
    Minimal Redis connectivity check.

    Intended for manual verification during Task 001.
    """

    client = redis.Redis.from_url(settings.redis_url)
    client.ping()
    logger.info("Redis ping succeeded")
    return {"redis_connected": True}

