from __future__ import annotations

import logging
import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.db.models.candidate import Candidate
from app.db.models.candidate_sessions import CandidateSession

logger = logging.getLogger(__name__)


async def get_candidate_id_from_bearer_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> uuid.UUID:
    """
    Fake auth: `Authorization: Bearer <session_token>`.

    Returns the associated `candidate_id`.
    """

    if not authorization or not authorization.lower().startswith("bearer "):
        logger.warning("auth_failed reason=missing_or_malformed_authorization_header")
        raise HTTPException(status_code=401, detail="Missing bearer token") from None

    token_str = authorization.split(" ", 1)[1].strip()
    try:
        token = uuid.UUID(token_str)
    except ValueError:
        logger.warning("auth_failed reason=invalid_session_token_uuid")
        raise HTTPException(status_code=401, detail="Invalid session token") from None

    row = await session.execute(
        select(CandidateSession).where(CandidateSession.token == token),
    )
    session_row = row.scalar_one_or_none()
    if session_row is None:
        logger.warning("auth_failed reason=unknown_session_token")
        raise HTTPException(status_code=401, detail="Unknown session token") from None

    return session_row.candidate_id


async def get_candidate_by_bearer_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> Candidate:
    """
    Fake auth: `Authorization: Bearer <session_token>`.

    Returns the Candidate row associated with the token.
    """

    candidate_id = await get_candidate_id_from_bearer_token(
        authorization=authorization, session=session
    )
    row = await session.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = row.scalar_one_or_none()
    if candidate is None:
        logger.warning(
            "auth_failed reason=candidate_missing_for_session candidate_id=%s", candidate_id
        )
        raise HTTPException(status_code=404, detail="Candidate not found") from None
    return candidate

