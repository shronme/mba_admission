from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import TaskStatus
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TaskItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "task_items"
    __table_args__ = (
        Index("ix_task_items_candidate_id", "candidate_id"),
        Index("ix_task_items_candidate_status", "candidate_id", "status"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, name="task_status", native_enum=True),
        nullable=False,
        default=TaskStatus.TODO,
        insert_default=TaskStatus.TODO,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="task_items")
