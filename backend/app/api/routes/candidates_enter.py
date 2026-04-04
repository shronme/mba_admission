"""
Legacy candidate entry point: POST /candidates/enter
Kept for backwards compatibility. Delegates to the same User+Candidate creation logic.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps.auth import get_candidate_id_from_bearer_token
from app.core.db import get_db_session
from app.db.enums import UserRole
from app.db.models.candidate import Candidate, CandidateProfile
from app.constants.grad_program_focus import ALLOWED_GRAD_PROGRAM_FOCUS, GRAD_PROGRAM_FOCUS_TO_TYPE
from app.constants.graduate_programs_catalog import (
    INTAKE_OTHER_SCHOOL_SENTINEL,
    ORDERED_SCHOOL_NAMES,
    PROGRAMS_BY_SCHOOL,
)
from app.constants.target_us_schools import INTAKE_TARGET_SCHOOLS_MAX_SELECTIONS
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.user_repo import UserRepository
from app.schemas.candidates import (
    CandidateEnterRequest,
    CandidateEnterResponse,
    CandidateIntakeUpdate,
    CandidateIntakeStepUpdate,
    CandidateOut,
    CandidateProfileOut,
)

import uuid

router = APIRouter(prefix="/candidates", tags=["candidates"])
logger = logging.getLogger(__name__)


def _intake_school_tiers() -> tuple[list[str], list[str]]:
    names = list(ORDERED_SCHOOL_NAMES)
    mid = (len(names) + 1) // 2
    tier_1, tier_2 = names[:mid], names[mid:]
    tier_2 = [*tier_2, INTAKE_OTHER_SCHOOL_SENTINEL]
    return tier_1, tier_2


def _intake_programs_by_school_payload() -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for school, entries in PROGRAMS_BY_SCHOOL.items():
        rows: list[dict[str, str]] = []
        for e in entries:
            slug = e.get("slug")
            if not isinstance(slug, str) or slug not in ALLOWED_GRAD_PROGRAM_FOCUS:
                continue
            label = e.get("label")
            rows.append({"slug": slug, "label": str(label) if label is not None else slug})
        out[school] = rows
    return out


def _merge_intake_profile_attributes(attrs: dict[str, Any], body: CandidateIntakeUpdate) -> None:
    attrs["target_schools"] = body.target_schools
    attrs["school_program_selections"] = [
        s.model_dump(mode="json") for s in body.school_program_selections
    ]
    if INTAKE_OTHER_SCHOOL_SENTINEL in body.target_schools:
        tso = (body.target_schools_other or "").strip()
        attrs["target_schools_other"] = tso if tso else None
    else:
        attrs.pop("target_schools_other", None)

    if body.grad_program_focus == "other_graduate":
        gpo = (body.grad_program_focus_other or "").strip()
        attrs["grad_program_focus_other"] = gpo if gpo else None
    else:
        attrs.pop("grad_program_focus_other", None)

    if body.intake_test_scores is not None:
        attrs["intake_test_scores"] = body.intake_test_scores.model_dump(mode="json")


def _candidate_to_out(c: Candidate) -> CandidateOut:
    profile_out = None
    if c.profile is not None:
        profile_out = CandidateProfileOut.model_validate(c.profile)
    return CandidateOut(
        id=c.id,
        email=c.user.email,
        full_name=c.user.full_name,
        program_type=c.program_type.value,
        status=c.status.value,
        stage=c.stage.value,
        profile=profile_out,
    )


def _default_full_name(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    return re.sub(r"[._-]+", " ", local).title() or "Applicant"


class ProfileGapQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., description="Profile attribute key (e.g. core_identity).")
    question: str = Field(..., description="Targeted question to fill this gap.")


class ProfileReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_complete: bool
    completeness_score: int = Field(..., ge=0, le=100)
    missing: list[ProfileGapQuestion]


class ProfileGapAnswersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, str] = Field(
        ...,
        description="Map of profile attribute key -> candidate answer text.",
    )


@router.post("/enter", response_model=CandidateEnterResponse)
async def enter_with_email(
    body: CandidateEnterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateEnterResponse:
    email_norm = str(body.email).strip().lower()
    user_repo = UserRepository(session)

    existing_user = await user_repo.get_by_email_with_candidate_profile(email_norm)

    if existing_user is not None:
        if existing_user.role != UserRole.CANDIDATE:
            raise HTTPException(status_code=403, detail="This email is registered as an admin.")
        candidate = existing_user.candidate
        token = (await user_repo.create_session(existing_user.id)).token
        await session.commit()
        return CandidateEnterResponse(
            created=False,
            candidate=_candidate_to_out(candidate),
            session_token=str(token),
        )

    full_name = (body.full_name or "").strip() or _default_full_name(email_norm)
    created_user_id: uuid.UUID | None = None
    try:
        new_user = await user_repo.create_user(
            email=email_norm,
            full_name=full_name,
            role=UserRole.CANDIDATE,
        )
        candidate_repo = CandidateRepository(session)
        candidate = await candidate_repo.create_candidate(user_id=new_user.id)
        await session.commit()
        await session.refresh(candidate, ["profile", "user"])
        created_user_id = new_user.id
    except IntegrityError:
        await session.rollback()
        race_user = await user_repo.get_by_email_with_candidate_profile(email_norm)
        if race_user is None:
            raise HTTPException(status_code=409, detail="Could not create account; try again.") from None
        candidate = race_user.candidate
        created_user_id = race_user.id

    token = (await user_repo.create_session(created_user_id)).token  # type: ignore[arg-type]
    await session.commit()

    return CandidateEnterResponse(
        created=created_user_id is not None,
        candidate=_candidate_to_out(candidate),
        session_token=str(token),
    )


@router.get("/intake/target-schools", response_model=None)
async def list_intake_target_schools(
    _candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
) -> dict[str, Any]:
    """Schools and per-school program slugs for intake — from graduate_programs_by_school.json."""
    tier_1, tier_2 = _intake_school_tiers()
    return {
        "tier_1": list(tier_1),
        "tier_2": list(tier_2),
        "max_selections": INTAKE_TARGET_SCHOOLS_MAX_SELECTIONS,
        "programs_by_school": _intake_programs_by_school_payload(),
        "other_school_value": INTAKE_OTHER_SCHOOL_SENTINEL,
    }


@router.get("/me", response_model=CandidateOut)
async def get_me(
    candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> CandidateOut:
    from sqlalchemy import select

    result = await session.execute(
        select(Candidate)
        .options(
            selectinload(Candidate.profile),
            selectinload(Candidate.user),
        )
        .where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return _candidate_to_out(candidate)


@router.patch("/me/intake", response_model=CandidateOut)
async def patch_me_intake(
    body: CandidateIntakeUpdate,
    candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> CandidateOut:
    from sqlalchemy import select

    result = await session.execute(
        select(Candidate)
        .options(
            selectinload(Candidate.profile),
            selectinload(Candidate.user),
        )
        .where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    user_repo = UserRepository(session)
    await user_repo.update_full_name(candidate.user_id, body.full_name)
    candidate.program_type = GRAD_PROGRAM_FOCUS_TO_TYPE[body.grad_program_focus]

    profile = candidate.profile
    if profile is None:
        profile = CandidateProfile(candidate_id=candidate.id)
        session.add(profile)
        candidate.profile = profile

    profile.country_of_residence = body.country_of_residence.strip()
    profile.date_of_birth = body.date_of_birth
    profile.grad_program_focus = body.grad_program_focus
    attrs = dict(profile.attributes or {})
    _merge_intake_profile_attributes(attrs, body)
    profile.attributes = attrs
    profile.intake_form_completed = True

    await session.commit()
    await session.refresh(candidate, ["profile", "user"])
    logger.info("candidate_intake_completed candidate_id=%s", candidate_id)
    return _candidate_to_out(candidate)


@router.patch("/me/intake/draft", response_model=CandidateOut)
async def patch_me_intake_draft(
    body: CandidateIntakeUpdate,
    candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> CandidateOut:
    """Save Step 1 intake answers without marking intake complete."""
    from sqlalchemy import select

    result = await session.execute(
        select(Candidate)
        .options(
            selectinload(Candidate.profile),
            selectinload(Candidate.user),
        )
        .where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    user_repo = UserRepository(session)
    await user_repo.update_full_name(candidate.user_id, body.full_name)
    candidate.program_type = GRAD_PROGRAM_FOCUS_TO_TYPE[body.grad_program_focus]

    profile = candidate.profile
    if profile is None:
        profile = CandidateProfile(candidate_id=candidate.id)
        session.add(profile)
        candidate.profile = profile

    profile.country_of_residence = body.country_of_residence.strip()
    profile.date_of_birth = body.date_of_birth
    profile.grad_program_focus = body.grad_program_focus

    attrs = dict(profile.attributes or {})
    _merge_intake_profile_attributes(attrs, body)
    attrs["intake_step_completed"] = max(int(attrs.get("intake_step_completed") or 0), 1)
    profile.attributes = attrs

    # Do NOT set intake_form_completed here. This endpoint is for draft saves.
    await session.commit()
    await session.refresh(candidate, ["profile", "user"])
    logger.info("candidate_intake_draft_saved candidate_id=%s", candidate_id)
    return _candidate_to_out(candidate)


@router.patch("/me/intake/step", response_model=CandidateOut)
async def patch_me_intake_step(
    body: CandidateIntakeStepUpdate,
    candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> CandidateOut:
    """Persist step completion progress in profile.attributes."""
    from sqlalchemy import select

    result = await session.execute(
        select(Candidate)
        .options(
            selectinload(Candidate.profile),
            selectinload(Candidate.user),
        )
        .where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    profile = candidate.profile
    if profile is None:
        profile = CandidateProfile(candidate_id=candidate.id)
        session.add(profile)
        candidate.profile = profile

    attrs = dict(profile.attributes or {})
    current = int(attrs.get("intake_step_completed") or 0)
    attrs["intake_step_completed"] = max(current, int(body.intake_step_completed))
    profile.attributes = attrs

    await session.commit()
    await session.refresh(candidate, ["profile", "user"])
    logger.info(
        "candidate_intake_step_saved candidate_id=%s step=%s",
        candidate_id,
        body.intake_step_completed,
    )
    return _candidate_to_out(candidate)


def _gap_to_question(key: str) -> str:
    from app.dspy.profile_agent import PROFILE_ATTRIBUTE_SCHEMA

    desc = (PROFILE_ATTRIBUTE_SCHEMA.get(key) or "").strip()
    if desc:
        return f"To complete your profile, please answer this about your {key.replace('_', ' ')}:\n\n{desc}\n\nWrite 3–8 sentences with specific examples."
    return f"Please provide details for: {key.replace('_', ' ')}."


@router.get("/me/profile/review", response_model=ProfileReviewResponse)
async def review_profile_completeness(
    candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> ProfileReviewResponse:
    """
    Step 4 (Final Intake Review): run the ProfileAgent on the current profile and
    return only the missing/insufficient attributes as targeted questions.
    """
    from sqlalchemy import select
    from app.dspy.profile_agent import CANDIDATE_INPUT_ATTRIBUTES, run_profile_agent

    result = await session.execute(select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id))
    profile = result.scalar_one_or_none()
    attrs = dict(profile.attributes or {}) if profile is not None else {}
    stored_score = int(profile.completeness_score) if profile is not None else 0

    use_openai = (
        (os.getenv("DSPY_MODE") or "mock").lower() == "openai"
        and bool(os.getenv("OPENAI_API_KEY"))
    )
    is_complete, gaps, synthesized, score = run_profile_agent(
        attrs, use_openai=use_openai, min_score=stored_score
    )

    # Best-effort persist synthesized + score + completion flag so the UI and later chat are consistent.
    try:
        repo = CandidateRepository(session)
        if synthesized:
            await repo.merge_profile_attributes(candidate_id, synthesized, overwrite=True)
        await repo.set_profile_complete(candidate_id, complete=is_complete, score=score)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("profile_review_persist_failed candidate_id=%s", candidate_id)

    # Keep a stable ordering for the UI.
    ordered_gaps = [k for k in CANDIDATE_INPUT_ATTRIBUTES if k in set(gaps)]
    return ProfileReviewResponse(
        profile_complete=bool(is_complete),
        completeness_score=int(score),
        missing=[ProfileGapQuestion(key=k, question=_gap_to_question(k)) for k in ordered_gaps],
    )


@router.patch("/me/profile/answers", response_model=ProfileReviewResponse)
async def submit_profile_gap_answers(
    body: ProfileGapAnswersRequest,
    candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> ProfileReviewResponse:
    """
    Step 4 (Final Intake Review): accept targeted answers for missing attributes,
    merge them into profile.attributes, then re-run ProfileAgent and return the next
    set of required questions (if any).
    """
    from sqlalchemy import select
    from app.dspy.profile_agent import CANDIDATE_INPUT_ATTRIBUTES, run_profile_agent

    allowed = set(CANDIDATE_INPUT_ATTRIBUTES)
    updates: dict[str, str] = {}
    for k, v in (body.answers or {}).items():
        key = str(k).strip()
        if key not in allowed:
            continue
        text = str(v).strip()
        if text:
            updates[key] = text

    if not updates:
        raise HTTPException(status_code=400, detail="No valid answers provided.")

    repo = CandidateRepository(session)
    await repo.merge_profile_attributes(candidate_id, updates, overwrite=True)

    prof_res = await session.execute(select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id))
    profile = prof_res.scalar_one_or_none()
    attrs = dict(profile.attributes or {}) if profile is not None else dict(updates)
    stored_score = int(profile.completeness_score) if profile is not None else 0

    use_openai = (
        (os.getenv("DSPY_MODE") or "mock").lower() == "openai"
        and bool(os.getenv("OPENAI_API_KEY"))
    )
    is_complete, gaps, synthesized, score = run_profile_agent(
        attrs, use_openai=use_openai, min_score=stored_score
    )

    if synthesized:
        await repo.merge_profile_attributes(candidate_id, synthesized, overwrite=True)
    await repo.set_profile_complete(candidate_id, complete=is_complete, score=score)
    await session.commit()

    ordered_gaps = [k for k in CANDIDATE_INPUT_ATTRIBUTES if k in set(gaps)]
    return ProfileReviewResponse(
        profile_complete=bool(is_complete),
        completeness_score=int(score),
        missing=[ProfileGapQuestion(key=k, question=_gap_to_question(k)) for k in ordered_gaps],
    )
