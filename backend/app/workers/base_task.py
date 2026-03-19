"""
Celery base task for AI-style background work: logging, retries, correlation id.

Concrete tasks should use `@celery_app.task(bind=True, base=AiJobTask, ...)`.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from celery import Task
from celery.exceptions import Retry

from app.core.sync_db import sync_session_scope
from app.db.models.ai_run import AiRun
from app.workers.ai_run_sync import mark_ai_run_failed
from app.workers.payloads import merge_request_meta

logger = logging.getLogger(__name__)


class AiJobTask(Task):
    """
    Base Celery task with:

    - Automatic retry for common transient errors (network / broker blips).
    - Exponential backoff + jitter.
    - Structured logging with optional `correlation_id` inside `payload`.
    - Best-effort `ai_run` → FAILED on **final** failure when `payload['ai_run_id']`
      is present (Celery does not call `on_failure` between automatic retries).
    """

    abstract = True

    autoretry_for = (ConnectionError, TimeoutError, OSError)
    retry_kwargs = {"max_retries": 5, "countdown": 10}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    def _payload_dict(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any] | None:
        if kwargs.get("payload") is not None and isinstance(kwargs["payload"], dict):
            return kwargs["payload"]
        if args and isinstance(args[0], dict):
            return args[0]
        return None

    def _correlation_id(self, payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        cid = payload.get("correlation_id")
        return str(cid) if cid else None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        payload = self._payload_dict(args, kwargs)
        cid = self._correlation_id(payload)
        extra = {"celery_task_id": self.request.id, "correlation_id": cid or "-"}
        log = logging.LoggerAdapter(logger, extra)
        log.info("task_start name=%s retries=%s", self.name, self.request.retries)
        try:
            return super().__call__(*args, **kwargs)
        except Retry:
            log.info("task_retry name=%s", self.name)
            raise
        finally:
            log.info("task_end name=%s", self.name)

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        payload = self._payload_dict(args, kwargs)
        cid = self._correlation_id(payload)
        log = logging.LoggerAdapter(
            logger,
            {"celery_task_id": task_id, "correlation_id": cid or "-"},
        )
        log.exception("task_failure name=%s", self.name)

        if payload and payload.get("ai_run_id"):
            try:
                run_id = uuid.UUID(str(payload["ai_run_id"]))
                with sync_session_scope() as session:
                    mark_ai_run_failed(session, run_id, str(exc))
            except Exception:
                log.exception("on_failure: could not mark ai_run FAILED")


def attach_worker_meta_to_ai_run(
    *,
    ai_run_id: uuid.UUID,
    celery_task_id: str,
    correlation_id: str | None,
) -> None:
    """Persist Celery task id (and correlation id) under `ai_run.request['_meta']`."""

    with sync_session_scope() as session:
        row = session.get(AiRun, ai_run_id)
        if row is None:
            return
        current = dict(row.request) if isinstance(row.request, dict) else {}
        row.request = merge_request_meta(
            current,
            celery_task_id=celery_task_id,
            correlation_id=correlation_id,
        )
        session.flush()
