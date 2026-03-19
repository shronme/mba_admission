from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AiRunStatus, AiRunType
from app.db.models.ai_run import AiRun
from app.repositories.base import BaseRepository


class AiRunRepository(BaseRepository):
    async def create_queued(
        self,
        *,
        candidate_id: uuid.UUID | None,
        run_type: AiRunType,
        request: dict[str, Any] | None = None,
        model_name: str | None = None,
    ) -> AiRun:
        row = AiRun(
            candidate_id=candidate_id,
            run_type=run_type,
            status=AiRunStatus.QUEUED,
            request=request,
            model_name=model_name,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, run_id: uuid.UUID) -> AiRun | None:
        return await self.session.get(AiRun, run_id)

    async def list_recent_for_candidate(
        self,
        candidate_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[AiRun]:
        result = await self.session.execute(
            select(AiRun)
            .where(AiRun.candidate_id == candidate_id)
            .order_by(AiRun.created_at.desc())
            .limit(limit),
        )
        return list(result.scalars().all())
