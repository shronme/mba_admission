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
from app.schemas.intake_test_scores import IntakeTestScores


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


class IntakeSchoolProgramSelection(BaseModel):
    """A single (school, program) target selection from the intake catalog."""

    model_config = ConfigDict(extra="forbid")

    school: str = Field(..., min_length=1, max_length=256)
    school_other: str | None = Field(default=None, max_length=512)
    program_slug: str = Field(..., min_length=1, max_length=128)
    program_other: str | None = Field(default=None, max_length=256)


class CandidateIntakeUpdate(BaseModel):
    """First-login demographic intake (stored on User + Candidate + CandidateProfile)."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=1, max_length=255)
    country_of_residence: str = Field(..., min_length=1, max_length=128)
    date_of_birth: date
    # New canonical intake representation: up to 4 (school, program) pairs.
    school_program_selections: list[IntakeSchoolProgramSelection] = Field(
        ...,
        min_length=1,
        max_length=4,
        description="Up to 4 (school, program) selections. First entry drives program_type.",
    )
    undergrad_gpa: float | None = Field(
        default=None,
        ge=0,
        le=4,
        description="Optional undergraduate GPA on a 0.0–4.0 scale (stored in profile.attributes).",
    )

    # Derived/legacy fields used internally by routes + DB mapping.
    # Keep these for backward compatibility and for downstream code that expects them.
    grad_program_focus: str = Field(default="", min_length=0, max_length=128)
    target_schools: list[str] = Field(default_factory=list, max_length=INTAKE_TARGET_SCHOOLS_MAX_SELECTIONS)
    target_schools_other: str | None = Field(default=None, max_length=512)
    grad_program_focus_other: str | None = Field(default=None, max_length=256)
    intake_test_scores: IntakeTestScores | None = None

    @field_validator("grad_program_focus")
    @classmethod
    def grad_program_focus_allowed(cls, v: str) -> str:
        key = v.strip()
        if not key:
            return ""
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
        return out

    @model_validator(mode="after")
    def derive_and_validate_from_pairs(self) -> CandidateIntakeUpdate:
        sentinel = INTAKE_OTHER_SCHOOL_SENTINEL
        if not self.school_program_selections:
            raise ValueError("Select at least one school")

        # Normalize + validate each selection.
        normalized: list[IntakeSchoolProgramSelection] = []
        seen_pairs: set[tuple[str, str]] = set()
        target_schools: list[str] = []
        any_other_school_text: str | None = None

        for sel in self.school_program_selections:
            school = sel.school.strip()
            if school not in ALLOWED_TARGET_US_SCHOOLS:
                raise ValueError("Invalid or unsupported school selection")

            school_other = (sel.school_other or "").strip() or None
            if school == sentinel:
                if not school_other:
                    raise ValueError('Please describe your school when "Other" is selected.')
                if any_other_school_text is None:
                    any_other_school_text = school_other
            else:
                if school_other:
                    raise ValueError('Custom school text is only allowed when "Other" is selected.')

            program_slug = sel.program_slug.strip()
            if program_slug not in ALLOWED_GRAD_PROGRAM_FOCUS:
                raise ValueError("Invalid program selection")

            program_other = (sel.program_other or "").strip() or None
            if program_slug == "other_graduate":
                if not program_other:
                    raise ValueError('Please describe your program when "Other program" is selected.')
            else:
                if program_other:
                    raise ValueError('Custom program text is only allowed when "Other program" is selected.')

            # Catalog offer check when both school + program are catalog-defined.
            if school != sentinel and program_slug != "other_graduate":
                offered = program_slugs_for_schools([school])
                if program_slug not in offered:
                    raise ValueError("Selected program is not offered at the selected school")

            key = (school, program_slug)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            normalized.append(
                IntakeSchoolProgramSelection(
                    school=school,
                    school_other=school_other,
                    program_slug=program_slug,
                    program_other=program_other,
                )
            )
            if school not in target_schools:
                target_schools.append(school)

        if not normalized:
            raise ValueError("Select at least one school")

        # Derived fields: first selection drives program_type + legacy fields.
        self.school_program_selections = normalized
        self.target_schools = target_schools
        self.target_schools_other = any_other_school_text
        self.grad_program_focus = normalized[0].program_slug
        self.grad_program_focus_other = normalized[0].program_other if normalized[0].program_slug == "other_graduate" else None
        return self

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
