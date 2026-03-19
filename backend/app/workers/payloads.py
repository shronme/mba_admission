"""
Typed Celery job payloads (Pydantic).

Tasks receive JSON-serializable dicts from the broker; validate with
`Model.model_validate(payload)` at the start of each task.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseJobPayload(BaseModel):
    """Shared optional metadata for all AI jobs."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str | None = Field(
        default=None,
        description="End-to-end id (e.g. X-Request-ID); propagated into logs and ai_run.request._meta.",
    )


class SampleSleepJobPayload(BaseJobPayload):
    """
    Demo payload for Task 003 — simulates a short AI-style job with DB status updates.

    Future jobs (profile extraction, strategy, essay review) should follow the same pattern:
    pass `ai_run_id` created by the API, validate a dedicated Pydantic model, update `ai_runs`.
    """

    ai_run_id: uuid.UUID
    sleep_seconds: float = Field(default=1.0, ge=0.0, le=300.0)
    simulate_transient_fail: bool = Field(
        default=False,
        description="If true, raises ConnectionError on the first attempt to exercise Celery retries.",
    )


def merge_request_meta(
    request: dict[str, Any] | None,
    *,
    celery_task_id: str,
    correlation_id: str | None,
) -> dict[str, Any]:
    """Attach worker metadata under request['_meta'] for traceability."""

    base = dict(request) if request else {}
    meta = dict(base.get("_meta") or {})
    meta["celery_task_id"] = celery_task_id
    if correlation_id:
        meta["correlation_id"] = correlation_id
    base["_meta"] = meta
    return base
