from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class UserSession(Base, TimestampMixin):
    """Single session table for all user roles (replaces candidate_sessions)."""

    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_id", "user_id"),)

    token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="sessions")  # type: ignore[name-defined]  # noqa: F821
