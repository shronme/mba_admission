"""
Sample AI-style Celery job (Task 003): sleeps, updates `ai_runs`, supports retry demo.
"""

from __future__ import annotations

import logging
import time

from app.core.celery_app import celery_app
from app.core.sync_db import sync_session_scope
from app.db.enums import AiRunStatus
from app.workers.ai_run_sync import get_ai_run, mark_ai_run_running, mark_ai_run_succeeded
from app.workers.base_task import AiJobTask, attach_worker_meta_to_ai_run
from app.workers.payloads import SampleSleepJobPayload

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=AiJobTask, name="app.jobs.sample_sleep")
def sample_sleep_ai_job(self, payload: dict) -> dict:
    """
    Validates `SampleSleepJobPayload`, moves `ai_run` QUEUED→RUNNING→SUCCEEDED.

    Set `simulate_transient_fail=true` on the first invocation to raise
    `ConnectionError` once so Celery's `autoretry_for` path is exercised.
    """

    data = SampleSleepJobPayload.model_validate(payload)
    logger.info(
        "sample_sleep task_start ai_run_id=%s sleep_seconds=%s simulate_transient_fail=%s correlation_id=%s",
        data.ai_run_id,
        data.sleep_seconds,
        data.simulate_transient_fail,
        data.correlation_id,
    )

    attach_worker_meta_to_ai_run(
        ai_run_id=data.ai_run_id,
        celery_task_id=self.request.id,
        correlation_id=data.correlation_id,
    )

    with sync_session_scope() as session:
        run = get_ai_run(session, data.ai_run_id)
        if run is None:
            raise ValueError(f"ai_run not found: {data.ai_run_id}")
        if run.status == AiRunStatus.SUCCEEDED:
            logger.info(
                "sample_sleep: idempotent skip (already SUCCEEDED) ai_run_id=%s",
                data.ai_run_id,
            )
            return {"ai_run_id": str(data.ai_run_id), "skipped": True}

        mark_ai_run_running(session, data.ai_run_id)

    if data.simulate_transient_fail and self.request.retries == 0:
        raise ConnectionError("simulated transient failure for retry demo")

    time.sleep(data.sleep_seconds)

    with sync_session_scope() as session:
        mark_ai_run_succeeded(
            session,
            data.ai_run_id,
            response={
                "kind": "sample_sleep",
                "slept_seconds": data.sleep_seconds,
                "celery_retries_used": self.request.retries,
            },
        )

    logger.info(
        "sample_sleep task_succeeded ai_run_id=%s celery_task_id=%s",
        data.ai_run_id,
        self.request.id,
    )
    return {
        "ai_run_id": str(data.ai_run_id),
        "status": "succeeded",
        "celery_task_id": self.request.id,
    }
