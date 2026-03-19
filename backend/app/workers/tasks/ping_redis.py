import logging

import redis

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.ping_redis")
def ping_redis() -> dict:
    """
    Minimal Redis connectivity check.

    Intended for manual verification during Task 001.
    """

    client = redis.Redis.from_url(settings.redis_url)
    client.ping()
    logger.info("Redis ping succeeded")
    return {"redis_connected": True}

