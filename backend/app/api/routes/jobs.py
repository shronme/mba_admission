"""
Enqueue and inspect background AI jobs (Celery + `ai_runs`).

Task 003: sample sleep job demonstrates retries, DB status updates, correlation id.
"""

from __future__ import annotations

import uuid

import redis
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.db import get_db_session
from app.db.enums import AiRunType
from app.repositories.ai_run_repo import AiRunRepository
from app.schemas.jobs import AiRunStatusRead, SampleSleepEnqueueBody, SampleSleepEnqueueResponse
from app.workers.tasks.sample_ai_job_task import sample_sleep_ai_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _check_broker() -> None:
    try:
        redis.Redis.from_url(settings.redis_url).ping()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={"error": "Redis unreachable", "message": str(e)},
        ) from e
    try:
        with celery_app.connection() as conn:
            conn.ensure_connection(max_retries=1)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={"error": "Celery broker unreachable", "message": str(e)},
        ) from e


@router.post("/sample-sleep", response_model=SampleSleepEnqueueResponse)
async def enqueue_sample_sleep(
    body: SampleSleepEnqueueBody,
    session: AsyncSession = Depends(get_db_session),
) -> SampleSleepEnqueueResponse:
    """
    Create an `ai_run` row (QUEUED) and enqueue the sample Celery task.

    Poll `GET /jobs/ai-runs/{ai_run_id}` for lifecycle: QUEUED → RUNNING → SUCCEEDED/FAILED.
    """

    _check_broker()

    repo = AiRunRepository(session)
    run = await repo.create_queued(
        candidate_id=body.candidate_id,
        run_type=AiRunType.OTHER,
        request={
            "kind": "sample_sleep",
            "sleep_seconds": body.sleep_seconds,
            "simulate_transient_fail": body.simulate_transient_fail,
        },
        model_name="sample_sleep",
    )
    await session.commit()

    payload = {
        "ai_run_id": str(run.id),
        "sleep_seconds": body.sleep_seconds,
        "correlation_id": body.correlation_id,
        "simulate_transient_fail": body.simulate_transient_fail,
    }
    async_result = sample_sleep_ai_job.delay(payload)
    return SampleSleepEnqueueResponse(ai_run_id=run.id, celery_task_id=async_result.id)


@router.get("/ai-runs/{run_id}", response_model=AiRunStatusRead)
async def get_ai_run_status(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AiRunStatusRead:
    repo = AiRunRepository(session)
    row = await repo.get(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ai_run not found")
    return AiRunStatusRead.from_orm_row(row)


@router.get("/celery/{task_id}")
def get_celery_task_meta(task_id: str) -> dict:
    """Thin wrapper around Celery result backend (useful with sample jobs)."""

    async_result = AsyncResult(task_id, app=celery_app)
    out: dict = {"task_id": task_id, "state": async_result.state}
    if async_result.ready():
        out["result"] = async_result.result
    elif async_result.failed():
        out["error"] = str(async_result.result)
    return out
