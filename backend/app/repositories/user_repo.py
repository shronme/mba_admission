from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.enums import UserRole
from app.db.models.user import User
from app.db.models.user_session import UserSession
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(func.lower(User.email) == email.strip().lower()),
        )
        return result.scalar_one_or_none()

    async def get_by_email_with_candidate_profile(self, email: str) -> User | None:
        """Eager-loads candidate → profile for the enter/login flow."""
        from app.db.models.candidate import Candidate, CandidateProfile

        result = await self.session.execute(
            select(User)
            .options(
                selectinload(User.candidate).selectinload(Candidate.profile),
            )
            .where(func.lower(User.email) == email.strip().lower()),
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_token(self, token: uuid.UUID) -> User | None:
        """Resolve a UserSession token → User (with candidate/admin eager-loaded)."""
        result = await self.session.execute(
            select(User)
            .join(UserSession, UserSession.user_id == User.id)
            .options(
                selectinload(User.candidate),
                selectinload(User.admin),
            )
            .where(UserSession.token == token),
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        *,
        email: str,
        full_name: str,
        role: UserRole,
    ) -> User:
        user = User(email=email.strip().lower(), full_name=full_name, role=role)
        self.session.add(user)
        await self.session.flush()
        return user

    async def create_session(self, user_id: uuid.UUID) -> UserSession:
        token = uuid.uuid4()
        sess = UserSession(token=token, user_id=user_id)
        self.session.add(sess)
        await self.session.flush()
        return sess
