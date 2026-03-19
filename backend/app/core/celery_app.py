from __future__ import annotations

import logging

from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)


def create_celery_app() -> Celery:
    task_modules = [
        "app.workers.tasks.ping_redis",
        "app.workers.tasks.wiring_smoke_task",
    ]
    celery_app = Celery(
        "app",
        broker=settings.celery_broker_url(),
        backend=settings.celery_result_backend(),
        include=task_modules,
    )

    # Keep config minimal for Task 001.
    celery_app.conf.update(
        broker_url=settings.celery_broker_url(),
        result_backend=settings.celery_result_backend(),
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_default_queue=settings.celery_task_default_queue,
        # Broker retry strategy helps local/dev startup ordering.
        broker_connection_retry_on_startup=True,
    )

    # Explicitly importing task modules via `include` is enough for Task 001.
    # Autodiscover is kept for future tasks if you add more modules.
    celery_app.autodiscover_tasks(["app.workers.tasks"])

    logger.info("Celery app configured with Redis broker/result")
    return celery_app


celery_app = create_celery_app()

