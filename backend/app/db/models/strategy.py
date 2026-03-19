from __future__ import annotations

import uuid

from sqlalchemy import Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import StrategyStatus, StrategyType
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class StrategyDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "strategy_decisions"
    __table_args__ = (
        Index("ix_strategy_decisions_candidate_id", "candidate_id"),
        Index("ix_strategy_decisions_type", "strategy_type"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    strategy_type: Mapped[StrategyType] = mapped_column(
        SQLEnum(StrategyType, name="strategy_type", native_enum=True),
        nullable=False,
    )
    status: Mapped[StrategyStatus] = mapped_column(
        SQLEnum(StrategyStatus, name="strategy_status", native_enum=True),
        nullable=False,
        default=StrategyStatus.DRAFT,
        insert_default=StrategyStatus.DRAFT,
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="strategy_decisions")
