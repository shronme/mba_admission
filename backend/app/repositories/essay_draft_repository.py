from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.enums import EssayStatus
from app.db.models.essay import EssayDraft
from app.repositories.base import BaseRepository


class EssayDraftRepository(BaseRepository):
    async def create(
        self,
        candidate_id: uuid.UUID,
        *,
        school_name: str | None,
        title: str,
        body: str,
        prompt_text: str | None = None,
        status: EssayStatus = EssayStatus.DRAFT,
        source: str = "human",
        extra: dict | None = None,
    ) -> EssayDraft:
        record = EssayDraft(
            candidate_id=candidate_id,
            school_name=school_name,
            title=title,
            body=body,
            prompt_text=prompt_text,
            status=status,
            source=source,
            extra=extra,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_id(self, artifact_id: uuid.UUID, *, candidate_id: uuid.UUID) -> EssayDraft | None:
        result = await self.session.execute(
            select(EssayDraft)
            .where(EssayDraft.id == artifact_id)
            .where(EssayDraft.candidate_id == candidate_id),
        )
        return result.scalar_one_or_none()

