"""
Enqueue and inspect background AI jobs (`ai_runs` + in-process runner).

Task 003: sample sleep job demonstrates retries, DB status updates, correlation id.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.db.enums import AiRunType
from app.repositories.ai_run_repo import AiRunRepository
from app.schemas.jobs import AiRunStatusRead, SampleSleepEnqueueBody, SampleSleepEnqueueResponse
from app.core.job_runner import JobType, job_runner

router = APIRouter(prefix="/jobs", tags=["jobs"])

logger = logging.getLogger(__name__)

@router.post("/sample-sleep", response_model=SampleSleepEnqueueResponse)
async def enqueue_sample_sleep(
    request: Request,
    body: SampleSleepEnqueueBody,
    session: AsyncSession = Depends(get_db_session),
) -> SampleSleepEnqueueResponse:
    """
    Create an `ai_run` row (QUEUED) and enqueue the sample Celery task.

    Poll `GET /jobs/ai-runs/{ai_run_id}` for lifecycle: QUEUED → RUNNING → SUCCEEDED/FAILED.
    """

    effective_correlation_id = body.correlation_id
    if effective_correlation_id is None:
        effective_correlation_id = getattr(request.state, "correlation_id", None)

    logger.info(
        "jobs_enqueue_sample_sleep start candidate_id=%s sleep_seconds=%s correlation_id=%s simulate_transient_fail=%s",
        body.candidate_id,
        body.sleep_seconds,
        effective_correlation_id,
        body.simulate_transient_fail,
    )

    repo = AiRunRepository(session)
    run = await repo.create_queued(
        candidate_id=body.candidate_id,
        run_type=AiRunType.OTHER,
        request={
            "kind": "sample_sleep",
            "sleep_seconds": body.sleep_seconds,
            "simulate_transient_fail": body.simulate_transient_fail,
            "correlation_id": effective_correlation_id,
        },
        model_name="sample_sleep",
    )
    await session.commit()

    payload = {
        "ai_run_id": str(run.id),
        "sleep_seconds": body.sleep_seconds,
        "correlation_id": effective_correlation_id,
        "simulate_transient_fail": body.simulate_transient_fail,
    }
    try:
        job_runner.enqueue(JobType.SAMPLE_SLEEP, payload)
    except Exception as e:  # noqa: BLE001
        logger.exception("jobs_enqueue_sample_sleep enqueue_failed ai_run_id=%s", run.id)
        raise HTTPException(status_code=503, detail={"error": "enqueue_failed", "message": str(e)})

    logger.info("jobs_enqueue_sample_sleep enqueued ai_run_id=%s", run.id)
    return SampleSleepEnqueueResponse(ai_run_id=run.id, celery_task_id=None)


@router.get("/ai-runs/{run_id}", response_model=AiRunStatusRead)
async def get_ai_run_status(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AiRunStatusRead:
    logger.info("jobs_get_ai_run_status run_id=%s", run_id)
    repo = AiRunRepository(session)
    row = await repo.get(run_id)
    if row is None:
        logger.warning("jobs_get_ai_run_status not_found run_id=%s", run_id)
        raise HTTPException(status_code=404, detail="ai_run not found")
    return AiRunStatusRead.from_orm_row(row)


@router.get("/celery/{task_id}")
def get_celery_task_meta(task_id: str) -> dict:
    raise HTTPException(status_code=410, detail="Celery task metadata is no longer available.")
