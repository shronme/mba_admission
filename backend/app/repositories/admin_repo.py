from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models.admin import Admin
from app.repositories.base import BaseRepository


class AdminRepository(BaseRepository):
    async def get_by_user_id(self, user_id: uuid.UUID) -> Admin | None:
        result = await self.session.execute(
            select(Admin).where(Admin.user_id == user_id),
        )
        return result.scalar_one_or_none()

    async def create_admin(self, user_id: uuid.UUID) -> Admin:
        admin = Admin(user_id=user_id)
        self.session.add(admin)
        await self.session.flush()
        return admin
