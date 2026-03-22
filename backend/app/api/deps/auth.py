from __future__ import annotations

import logging
import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.db.enums import UserRole
from app.db.models.user import User
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


def _parse_bearer_token(authorization: str | None) -> uuid.UUID:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token_str = authorization.split(" ", 1)[1].strip()
    try:
        return uuid.UUID(token_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session token") from None


async def get_user_from_bearer_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Resolve a UserSession token → User (with candidate + admin eagerly loaded)."""
    token = _parse_bearer_token(authorization)
    repo = UserRepository(session)
    user = await repo.get_by_token(token)
    if user is None:
        logger.warning("auth_failed reason=unknown_session_token")
        raise HTTPException(status_code=401, detail="Unknown session token")
    return user


async def get_candidate_id_from_bearer_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> uuid.UUID:
    """
    Candidate-scoped auth: token → User (role=candidate) → candidate_id.
    Kept for backwards compatibility with all existing candidate routes.
    """
    token = _parse_bearer_token(authorization)
    repo = UserRepository(session)
    user = await repo.get_by_token(token)
    if user is None:
        logger.warning("auth_failed reason=unknown_session_token")
        raise HTTPException(status_code=401, detail="Unknown session token")
    if user.role != UserRole.CANDIDATE:
        logger.warning("auth_failed reason=wrong_role role=%s", user.role)
        raise HTTPException(status_code=403, detail="Candidate access required")
    if user.candidate is None:
        logger.warning("auth_failed reason=missing_candidate_row user_id=%s", user.id)
        raise HTTPException(status_code=500, detail="Candidate record not found")
    return user.candidate.id


async def get_admin_from_bearer_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Admin-scoped auth: token → User (role=admin)."""
    token = _parse_bearer_token(authorization)
    repo = UserRepository(session)
    user = await repo.get_by_token(token)
    if user is None:
        logger.warning("admin_auth_failed reason=unknown_session_token")
        raise HTTPException(status_code=401, detail="Unknown session token")
    if user.role != UserRole.ADMIN:
        logger.warning("admin_auth_failed reason=wrong_role role=%s", user.role)
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
