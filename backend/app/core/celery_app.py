from __future__ import annotations

import logging

from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "app",
    broker=settings.celery_broker_url(),
    backend=settings.celery_result_backend(),
)

celery_app.conf.update(
    broker_url=settings.celery_broker_url(),
    result_backend=settings.celery_result_backend(),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue=settings.celery_task_default_queue,
    broker_connection_retry_on_startup=True,
)

# Import task modules **after** `celery_app` exists so `@celery_app.task` registers
# on this app (plain `shared_task` can bind to the wrong default app).
import app.workers.tasks.ping_redis  # noqa: E402, F401
import app.workers.tasks.sample_ai_job_task  # noqa: E402, F401
import app.workers.tasks.wiring_smoke_task  # noqa: E402, F401

logger.info("Celery app configured with Redis broker/result")
