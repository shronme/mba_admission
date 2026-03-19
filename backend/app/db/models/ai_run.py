from __future__ import annotations

import uuid

from sqlalchemy import Enum as SQLEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import AiRunStatus, AiRunType
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AiRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_runs"
    __table_args__ = (
        Index("ix_ai_runs_candidate_id", "candidate_id"),
        Index("ix_ai_runs_status", "status"),
        Index("ix_ai_runs_run_type", "run_type"),
    )

    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=True,
    )
    run_type: Mapped[AiRunType] = mapped_column(
        SQLEnum(AiRunType, name="ai_run_type", native_enum=True),
        nullable=False,
    )
    status: Mapped[AiRunStatus] = mapped_column(
        SQLEnum(AiRunStatus, name="ai_run_status", native_enum=True),
        nullable=False,
        default=AiRunStatus.QUEUED,
        insert_default=AiRunStatus.QUEUED,
    )
    request: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate: Mapped["Candidate | None"] = relationship(back_populates="ai_runs")
