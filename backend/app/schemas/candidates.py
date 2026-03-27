"""API schemas for candidate-facing flows (fake login / enter)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants.grad_program_focus import ALLOWED_GRAD_PROGRAM_FOCUS


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
    country_of_residence: str | None = None
    date_of_birth: date | None = None
    intake_form_completed: bool = False
    grad_program_focus: str | None = None


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


class CandidateIntakeUpdate(BaseModel):
    """First-login demographic intake (stored on User + Candidate + CandidateProfile)."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=1, max_length=255)
    country_of_residence: str = Field(..., min_length=1, max_length=128)
    date_of_birth: date
    grad_program_focus: str = Field(..., min_length=1, max_length=128)

    @field_validator("grad_program_focus")
    @classmethod
    def grad_program_focus_allowed(cls, v: str) -> str:
        key = v.strip()
        if key not in ALLOWED_GRAD_PROGRAM_FOCUS:
            raise ValueError("Invalid program selection")
        return key

    @field_validator("date_of_birth")
    @classmethod
    def dob_reasonable(cls, v: date) -> date:
        today = date.today()
        if v > today:
            raise ValueError("date_of_birth cannot be in the future")
        if v.year < 1900:
            raise ValueError("date_of_birth is too far in the past")
        return v
