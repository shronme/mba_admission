"""
Unified auth entry point: POST /auth/enter

Looks up the email in the `users` table:
- role=admin  → creates AdminSession, returns role="admin"
- role=candidate → creates UserSession, returns role="candidate"
- not found → creates User (role=candidate) + Candidate, creates UserSession
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.db.enums import UserRole
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.user_repo import UserRepository
from app.schemas.candidates import CandidateOut, CandidateProfileOut
from app.db.models.candidate import Candidate

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AuthEnterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)


class AdminUserOut(BaseModel):
    id: str
    email: str
    full_name: str


class AuthEnterResponse(BaseModel):
    role: str
    session_token: str
    admin: AdminUserOut | None = None
    candidate: CandidateOut | None = None
    created: bool = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_full_name(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    return re.sub(r"[._-]+", " ", local).title() or "Applicant"


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


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/enter", response_model=AuthEnterResponse)
async def auth_enter(
    body: AuthEnterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthEnterResponse:
    email_norm = str(body.email).strip().lower()
    user_repo = UserRepository(session)

    # ── Existing user ─────────────────────────────────────────────────────────
    existing_user = await user_repo.get_by_email_with_candidate_profile(email_norm)

    if existing_user is not None:
        user_session = await user_repo.create_session(existing_user.id)
        await session.commit()

        if existing_user.role == UserRole.ADMIN:
            logger.info("auth_enter admin_login user_id=%s", existing_user.id)
            return AuthEnterResponse(
                role="admin",
                session_token=str(user_session.token),
                admin=AdminUserOut(
                    id=str(existing_user.id),
                    email=existing_user.email,
                    full_name=existing_user.full_name,
                ),
            )

        # role=candidate
        candidate = existing_user.candidate
        logger.info("auth_enter candidate_login user_id=%s", existing_user.id)
        return AuthEnterResponse(
            role="candidate",
            session_token=str(user_session.token),
            candidate=_candidate_to_out(candidate) if candidate else None,
        )

    # ── New candidate ─────────────────────────────────────────────────────────
    full_name = (body.full_name or "").strip() or _default_full_name(email_norm)
    try:
        new_user = await user_repo.create_user(
            email=email_norm,
            full_name=full_name,
            role=UserRole.CANDIDATE,
        )
        candidate_repo = CandidateRepository(session)
        new_candidate = await candidate_repo.create_candidate(user_id=new_user.id)
        await session.commit()
        await session.refresh(new_candidate, ["profile", "user"])
    except IntegrityError:
        await session.rollback()
        # Race: another request created the same email — retry lookup
        existing_user = await user_repo.get_by_email_with_candidate_profile(email_norm)
        if existing_user is None:
            raise HTTPException(status_code=409, detail="Could not create account; try again.") from None
        user_session = await user_repo.create_session(existing_user.id)
        await session.commit()
        return AuthEnterResponse(
            role=existing_user.role.value,
            session_token=str(user_session.token),
            candidate=_candidate_to_out(existing_user.candidate) if existing_user.candidate else None,
        )

    user_session = await user_repo.create_session(new_user.id)
    await session.commit()

    logger.info("auth_enter candidate_created user_id=%s candidate_id=%s", new_user.id, new_candidate.id)
    return AuthEnterResponse(
        role="candidate",
        session_token=str(user_session.token),
        candidate=_candidate_to_out(new_candidate),
        created=True,
    )
