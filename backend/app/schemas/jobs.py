"""Pydantic schemas for job enqueue / status APIs."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SampleSleepEnqueueBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID | None = None
    sleep_seconds: float = Field(default=1.0, ge=0.0, le=300.0)
    correlation_id: str | None = Field(
        default=None,
        max_length=128,
        description="Optional id (e.g. X-Request-ID) for logs and ai_run.request._meta.",
    )
    simulate_transient_fail: bool = Field(
        default=False,
        description="Raises a transient error once so Celery retries fire (demo only).",
    )


class SampleSleepEnqueueResponse(BaseModel):
    ai_run_id: uuid.UUID
    celery_task_id: str


class AiRunStatusRead(BaseModel):
    """Subset of `ai_runs` for polling."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID | None
    run_type: str
    status: str
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    model_name: str | None = None
    error_message: str | None = None

    @classmethod
    def from_orm_row(cls, row: Any) -> AiRunStatusRead:
        return cls(
            id=row.id,
            candidate_id=row.candidate_id,
            run_type=row.run_type.value if hasattr(row.run_type, "value") else str(row.run_type),
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            request=row.request,
            response=row.response,
            model_name=row.model_name,
            error_message=row.error_message,
        )
