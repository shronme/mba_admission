from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.enums import StrategyStatus, StrategyType
from app.db.models.strategy import StrategyDecision
from app.repositories.base import BaseRepository


class StrategyDecisionRepository(BaseRepository):
    async def upsert_school_selection(
        self,
        candidate_id: uuid.UUID,
        *,
        payload: dict,
    ) -> StrategyDecision:
        result = await self.session.execute(
            select(StrategyDecision)
            .where(StrategyDecision.candidate_id == candidate_id)
            .where(StrategyDecision.strategy_type == StrategyType.SCHOOL_SELECTION),
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            existing = StrategyDecision(
                candidate_id=candidate_id,
                strategy_type=StrategyType.SCHOOL_SELECTION,
                status=StrategyStatus.ACTIVE,
                payload=payload,
            )
            self.session.add(existing)
            await self.session.flush()
            return existing

        existing.status = StrategyStatus.ACTIVE
        existing.payload = payload
        await self.session.flush()
        return existing

