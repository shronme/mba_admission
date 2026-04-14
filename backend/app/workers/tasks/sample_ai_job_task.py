"""
Sample AI-style Celery job (Task 003): sleeps, updates `ai_runs`, supports retry demo.
"""

from __future__ import annotations

import logging
import time

from app.core.sync_db import sync_session_scope
from app.db.enums import AiRunStatus
from app.workers.ai_run_sync import get_ai_run, mark_ai_run_running, mark_ai_run_succeeded
from app.workers.payloads import SampleSleepJobPayload

logger = logging.getLogger(__name__)


def sample_sleep_ai_job(payload: dict) -> dict:
    """
    Validates `SampleSleepJobPayload`, moves `ai_run` QUEUED→RUNNING→SUCCEEDED.

    Note: this used to demonstrate Celery retries; in-process execution does not
    retry automatically. If `simulate_transient_fail=true`, the run is marked FAILED.
    """

    data = SampleSleepJobPayload.model_validate(payload)
    logger.info(
        "sample_sleep task_start ai_run_id=%s sleep_seconds=%s simulate_transient_fail=%s correlation_id=%s",
        data.ai_run_id,
        data.sleep_seconds,
        data.simulate_transient_fail,
        data.correlation_id,
    )

    try:
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

        if data.simulate_transient_fail:
            raise ConnectionError("simulated transient failure (no in-process retry)")

        time.sleep(data.sleep_seconds)

        with sync_session_scope() as session:
            mark_ai_run_succeeded(
                session,
                data.ai_run_id,
                response={
                    "kind": "sample_sleep",
                    "slept_seconds": data.sleep_seconds,
                },
            )

        logger.info("sample_sleep task_succeeded ai_run_id=%s", data.ai_run_id)
        return {"ai_run_id": str(data.ai_run_id), "status": "succeeded"}
    except Exception as e:  # noqa: BLE001
        # Mark failed so `/jobs/ai-runs/{id}` reflects completion.
        from app.workers.ai_run_sync import mark_ai_run_failed

        with sync_session_scope() as session:
            mark_ai_run_failed(session, data.ai_run_id, str(e))
        raise
