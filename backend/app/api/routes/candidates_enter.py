"""
Fake login / session bootstrap: enter email → load candidate + profile or create one.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.db.models.candidate import Candidate
from app.repositories.candidate_repo import CandidateRepository
from app.schemas.candidates import (
    CandidateEnterRequest,
    CandidateEnterResponse,
    CandidateOut,
    CandidateProfileOut,
)

router = APIRouter(prefix="/candidates", tags=["candidates"])


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

    repo = CandidateRepository(session)

    existing = await repo.get_by_email_ci_with_profile(email_norm)
    if existing is not None:
        return CandidateEnterResponse(
            created=False,
            candidate=_candidate_to_out(existing),
        )

    full_name = (body.full_name or "").strip() or _default_full_name_from_email(email_norm)

    try:
        candidate = await repo.create_candidate(
            email=email_norm,
            full_name=full_name,
        )
        await session.commit()
        await session.refresh(candidate, ["profile"])
    except IntegrityError:
        # Race: another request created the same email first
        await session.rollback()
        existing = await repo.get_by_email_ci_with_profile(email_norm)
        if existing is None:
            raise HTTPException(
                status_code=409,
                detail="Could not create or load candidate; try again.",
            ) from None
        return CandidateEnterResponse(
            created=False,
            candidate=_candidate_to_out(existing),
        )

    return CandidateEnterResponse(
        created=True,
        candidate=_candidate_to_out(candidate),
    )
