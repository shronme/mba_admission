"""API schemas for candidate-facing flows (fake login / enter)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CandidateEnterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str | None = Field(
        default=None,
        max_length=255,
        description="Used when creating a new candidate; defaults from the email local part if omitted.",
    )


class CandidateProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    headline: str | None = None
    summary: str | None = None
    attributes: dict[str, Any] | None = None
    profile_complete: bool = False
    completeness_score: int = 0  # persisted by ProfileAgent; read directly from DB column


class CandidateOut(BaseModel):
    """Candidate view — email/full_name come from the joined User."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    full_name: str
    program_type: str
    status: str
    stage: str
    profile: CandidateProfileOut | None = None


class CandidateEnterResponse(BaseModel):
    """Login response for the legacy /candidates/enter endpoint."""

    created: bool
    candidate: CandidateOut
    session_token: str
