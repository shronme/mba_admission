"""
Sync helpers to create/update `ai_runs` from Celery tasks (uses `sync_session_scope`).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.enums import AiRunStatus, AiRunType
from app.db.models.ai_run import AiRun


def get_ai_run(session: Session, run_id: uuid.UUID) -> AiRun | None:
    return session.get(AiRun, run_id)


def create_ai_run_row(
    session: Session,
    *,
    candidate_id: uuid.UUID | None,
    run_type: AiRunType,
    request: dict[str, Any] | None,
    model_name: str | None = None,
    status: AiRunStatus = AiRunStatus.QUEUED,
) -> AiRun:
    row = AiRun(
        candidate_id=candidate_id,
        run_type=run_type,
        status=status,
        request=request,
        model_name=model_name,
    )
    session.add(row)
    session.flush()
    return row


def mark_ai_run_running(session: Session, run_id: uuid.UUID) -> AiRun | None:
    row = session.get(AiRun, run_id)
    if row is None:
        return None
    row.status = AiRunStatus.RUNNING
    row.error_message = None
    session.flush()
    return row


def mark_ai_run_succeeded(
    session: Session,
    run_id: uuid.UUID,
    *,
    response: dict[str, Any] | None,
) -> AiRun | None:
    row = session.get(AiRun, run_id)
    if row is None:
        return None
    row.status = AiRunStatus.SUCCEEDED
    row.response = response
    row.error_message = None
    session.flush()
    return row


def mark_ai_run_failed(
    session: Session,
    run_id: uuid.UUID,
    message: str,
) -> AiRun | None:
    row = session.get(AiRun, run_id)
    if row is None:
        return None
    row.status = AiRunStatus.FAILED
    row.error_message = message[:8000] if message else None
    session.flush()
    return row


def mark_ai_run_cancelled(session: Session, run_id: uuid.UUID) -> AiRun | None:
    row = session.get(AiRun, run_id)
    if row is None:
        return None
    row.status = AiRunStatus.CANCELLED
    session.flush()
    return row
