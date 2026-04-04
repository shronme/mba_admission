"""POST /candidates/me/admission-evaluation/start — enqueue admission evaluation job."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import redis
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_candidate_id_from_bearer_token
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.db import get_db_session
from app.db.enums import AiRunType
from app.db.models.candidate import CandidateProfile
from app.repositories.ai_run_repo import AiRunRepository
from app.repositories.candidate_repo import CandidateRepository
from app.workers.tasks.admission_evaluation_task import admission_evaluation_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates/me/admission-evaluation", tags=["candidates"])


class AdmissionEvaluationStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_run_id: uuid.UUID
    celery_task_id: str | None = None


def _check_broker() -> None:
    try:
        redis.Redis.from_url(settings.redis_url).ping()
    except Exception as e:  # noqa: BLE001
        logger.warning("admission_eval broker check redis_failed error=%s", str(e))
        raise HTTPException(
            status_code=503,
            detail={"error": "Redis unreachable", "message": str(e)},
        ) from e
    try:
        with celery_app.connection() as conn:
            conn.ensure_connection(max_retries=1)
    except Exception as e:  # noqa: BLE001
        logger.warning("admission_eval broker check celery_failed error=%s", str(e))
        raise HTTPException(
            status_code=503,
            detail={"error": "Celery broker unreachable", "message": str(e)},
        ) from e


@router.post("/start", response_model=AdmissionEvaluationStartResponse)
async def start_admission_evaluation(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
) -> AdmissionEvaluationStartResponse:
    """
    Enqueue per-program admission evaluation (research + evaluation).
    Idempotent: if a run is already queued/running, returns that ai_run_id.
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    if isinstance(correlation_id, str):
        cid: str | None = correlation_id
    else:
        cid = None

    prof = (
        await session.execute(
            select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id),
        )
    ).scalar_one_or_none()
    attrs = dict(prof.attributes or {}) if prof else {}

    if not prof or not prof.intake_form_completed:
        raise HTTPException(
            status_code=400,
            detail="Complete intake before starting evaluation.",
        )

    existing_job = attrs.get("admission_evaluation_job")
    if isinstance(existing_job, dict):
        phase = str(existing_job.get("phase") or "")
        if phase == "running":
            aid = existing_job.get("ai_run_id")
            if aid:
                try:
                    return AdmissionEvaluationStartResponse(
                        ai_run_id=uuid.UUID(str(aid)),
                        celery_task_id=None,
                    )
                except ValueError:
                    pass

    result = attrs.get("admission_evaluation_result")
    if isinstance(result, dict) and result.get("status") == "complete":
        raise HTTPException(
            status_code=409,
            detail="Admission evaluation already completed.",
        )

    _check_broker()

    repo = AiRunRepository(session)
    run = await repo.create_queued(
        candidate_id=candidate_id,
        run_type=AiRunType.REVIEW,
        request={
            "kind": "admission_evaluation",
            "correlation_id": cid,
        },
        model_name="admission_evaluation",
    )
    await session.commit()

    payload = {
        "ai_run_id": str(run.id),
        "candidate_id": str(candidate_id),
        "correlation_id": cid,
    }
    async_result = admission_evaluation_job.delay(payload)
    logger.info(
        "admission_evaluation enqueued ai_run_id=%s celery_task_id=%s",
        run.id,
        async_result.id,
    )

    sels = attrs.get("school_program_selections")
    n_sel = len(sels) if isinstance(sels, list) else 0

    crepo = CandidateRepository(session)
    await crepo.merge_profile_attributes(
        candidate_id,
        {
            "admission_evaluation_result": None,
            "admission_evaluation_job": {
                "ai_run_id": str(run.id),
                "phase": "running",
                "message": "Starting…",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "current_school": "",
                "current_program_display_name": "",
                "current_program_slug": "",
                "program_index": 0,
                "programs_total": n_sel,
                "substep": "research",
                "phase_scope": "primary",
                "progress_percent": 0,
                "programs_completed": [],
            },
        },
        overwrite=True,
    )
    await session.commit()

    return AdmissionEvaluationStartResponse(
        ai_run_id=run.id,
        celery_task_id=async_result.id,
    )
