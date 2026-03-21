"""
Fake login / session bootstrap: enter email → load candidate + profile or create one.
"""

from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_candidate_id_from_bearer_token
from app.core.db import get_db_session
from app.db.models.candidate import Candidate
from app.db.models.candidate_sessions import CandidateSession
from app.repositories.candidate_repo import CandidateRepository
from app.schemas.candidates import (
    CandidateEnterRequest,
    CandidateEnterResponse,
    CandidateOut,
    CandidateProfileOut,
)

router = APIRouter(prefix="/candidates", tags=["candidates"])

logger = logging.getLogger(__name__)


def _candidate_to_out(c: Candidate) -> CandidateOut:
    profile_out = None
    if c.profile is not None:
        profile_out = CandidateProfileOut.model_validate(c.profile)
    return CandidateOut(
        id=c.id,
        email=c.email,
        full_name=c.full_name,
        program_type=c.program_type.value,
        status=c.status.value,
        stage=c.stage.value,
        profile=profile_out,
    )


def _default_full_name_from_email(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    local = re.sub(r"[._-]+", " ", local)
    return local.title() if local else "Applicant"


@router.post("/enter", response_model=CandidateEnterResponse)
async def enter_with_email(
    body: CandidateEnterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateEnterResponse:
    """
    **Fake login** (no password): if a candidate with this email exists, return them + profile;
    otherwise create a candidate with optional `full_name` (or a placeholder derived from email).
    """

    email_norm = str(body.email).strip().lower()
    if not email_norm or "@" not in email_norm:
        raise HTTPException(status_code=400, detail="Invalid email")

    email_user, _, email_domain = email_norm.partition("@")
    email_user_safe = (email_user[:2] + "***") if email_user else "***"
    email_safe = f"{email_user_safe}@{email_domain}" if email_domain else "invalid"
    logger.info("candidate_enter start email=%s", email_safe)

    repo = CandidateRepository(session)

    existing = await repo.get_by_email_ci_with_profile(email_norm)
    created = False
    candidate: Candidate

    if existing is not None:
        candidate = existing
    else:
        full_name = (body.full_name or "").strip() or _default_full_name_from_email(email_norm)

        try:
            candidate = await repo.create_candidate(
                email=email_norm,
                full_name=full_name,
            )
            await session.commit()
            created = True
            await session.refresh(candidate, ["profile"])
        except IntegrityError:
            # Race: another request created the same email first
            logger.warning("candidate_enter integrity_race email=%s", email_safe)
            await session.rollback()
            existing = await repo.get_by_email_ci_with_profile(email_norm)
            if existing is None:
                raise HTTPException(
                    status_code=409,
                    detail="Could not create or load candidate; try again.",
                ) from None
            candidate = existing
            created = False

    # Always create a new fake session token per enter call.
    token = uuid.uuid4()
    session.add(
        CandidateSession(
            token=token,
            candidate_id=candidate.id,
        )
    )
    await session.commit()

    logger.info(
        "candidate_enter done created=%s candidate_id=%s",
        created,
        candidate.id,
    )
    return CandidateEnterResponse(
        created=created,
        candidate=_candidate_to_out(candidate),
        session_token=str(token),
    )


@router.get("/me", response_model=CandidateOut)
async def get_me(
    candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> CandidateOut:
    """Return the authenticated candidate with their current profile (for polling)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(Candidate)
        .options(selectinload(Candidate.profile))
        .where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return _candidate_to_out(candidate)
