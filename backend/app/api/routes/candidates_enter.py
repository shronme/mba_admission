"""
Legacy candidate entry point: POST /candidates/enter
Kept for backwards compatibility. Delegates to the same User+Candidate creation logic.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps.auth import get_candidate_id_from_bearer_token
from app.core.db import get_db_session
from app.db.enums import UserRole
from app.db.models.candidate import Candidate, CandidateProfile
from app.constants.grad_program_focus import GRAD_PROGRAM_FOCUS_TO_TYPE
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.user_repo import UserRepository
from app.schemas.candidates import (
    CandidateEnterRequest,
    CandidateEnterResponse,
    CandidateIntakeUpdate,
    CandidateOut,
    CandidateProfileOut,
)

import uuid

router = APIRouter(prefix="/candidates", tags=["candidates"])
logger = logging.getLogger(__name__)


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
    profile.intake_form_completed = True

    await session.commit()
    await session.refresh(candidate, ["profile", "user"])
    logger.info("candidate_intake_completed candidate_id=%s", candidate_id)
    return _candidate_to_out(candidate)
