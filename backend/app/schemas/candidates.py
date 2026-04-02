"""API schemas for candidate-facing flows (fake login / enter)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.constants.grad_program_focus import ALLOWED_GRAD_PROGRAM_FOCUS
from app.constants.graduate_programs_catalog import INTAKE_OTHER_SCHOOL_SENTINEL, program_slugs_for_schools
from app.constants.target_us_schools import (
    ALLOWED_TARGET_US_SCHOOLS,
    INTAKE_TARGET_SCHOOLS_MAX_SELECTIONS,
)


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
    target_schools: list[str] = Field(
        ...,
        min_length=1,
        max_length=INTAKE_TARGET_SCHOOLS_MAX_SELECTIONS,
        description="School names from the intake catalog, plus optional synthetic Other row.",
    )
    target_schools_other: str | None = Field(
        default=None,
        max_length=512,
        description='Required when target_schools includes the synthetic "Other" token.',
    )
    grad_program_focus_other: str | None = Field(
        default=None,
        max_length=256,
        description='Required when grad_program_focus is "other_graduate".',
    )

    @field_validator("grad_program_focus")
    @classmethod
    def grad_program_focus_allowed(cls, v: str) -> str:
        key = v.strip()
        if key not in ALLOWED_GRAD_PROGRAM_FOCUS:
            raise ValueError("Invalid program selection")
        return key

    @field_validator("target_schools")
    @classmethod
    def target_schools_allowed(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for raw in v:
            name = raw.strip()
            if not name:
                continue
            if name not in ALLOWED_TARGET_US_SCHOOLS:
                raise ValueError("Invalid or unsupported school selection")
            if name not in seen:
                seen.add(name)
                out.append(name)
        if not out:
            raise ValueError("Select at least one target school")
        return out

    @model_validator(mode="after")
    def intake_other_school_and_program_rules(self) -> CandidateIntakeUpdate:
        sentinel = INTAKE_OTHER_SCHOOL_SENTINEL
        has_other_school = sentinel in self.target_schools
        catalog_schools = [s for s in self.target_schools if s != sentinel]

        if not has_other_school and (self.target_schools_other or "").strip():
            raise ValueError('Custom school text is only allowed when "Other" is selected.')

        if has_other_school:
            if not (self.target_schools_other or "").strip():
                raise ValueError('Please describe your school when "Other" is selected.')

        if self.grad_program_focus == "other_graduate":
            if not (self.grad_program_focus_other or "").strip():
                raise ValueError('Please describe your program when "Other program" is selected.')
            return self

        if not catalog_schools:
            return self

        offered = program_slugs_for_schools(catalog_schools)
        if self.grad_program_focus in offered:
            return self

        if has_other_school:
            raise ValueError(
                "This program is not listed for your selected catalog schools. "
                'Choose "Other program" and describe it, or change schools or program.'
            )
        raise ValueError("Selected program is not offered at any of your target schools")

    @field_validator("date_of_birth")
    @classmethod
    def dob_reasonable(cls, v: date) -> date:
        today = date.today()
        if v > today:
            raise ValueError("date_of_birth cannot be in the future")
        if v.year < 1900:
            raise ValueError("date_of_birth is too far in the past")
        return v


class CandidateIntakeStepUpdate(BaseModel):
    """Persist front-end intake step progress without completing the intake."""

    model_config = ConfigDict(extra="forbid")

    intake_step_completed: int = Field(..., ge=0, le=4)
