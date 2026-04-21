from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models.cv_draft import CVDraft
from app.repositories.base import BaseRepository


class CVDraftRepository(BaseRepository):
    async def create(
        self,
        candidate_id: uuid.UUID,
        *,
        school_name: str | None,
        title: str,
        body: str,
        extra: dict | None = None,
    ) -> CVDraft:
        result = await self.session.execute(
            select(func.coalesce(func.max(CVDraft.version), 0))
            .where(CVDraft.candidate_id == candidate_id)
            .where(CVDraft.school_name == school_name),
        )
        current_max: int = int(result.scalar_one())
        next_version = current_max + 1

        record = CVDraft(
            candidate_id=candidate_id,
            school_name=school_name,
            title=title,
            body=body,
            version=next_version,
            status="draft",
            extra=extra,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_id(self, artifact_id: uuid.UUID, *, candidate_id: uuid.UUID) -> CVDraft | None:
        result = await self.session.execute(
            select(CVDraft)
            .where(CVDraft.id == artifact_id)
            .where(CVDraft.candidate_id == candidate_id),
        )
        return result.scalar_one_or_none()

