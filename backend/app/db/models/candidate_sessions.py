from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class CandidateSession(Base, TimestampMixin):
    """
    Fake auth session for the FE scaffold.

    Stores a server-side mapping from `session_token` to `candidate_id`.
    """

    __tablename__ = "candidate_sessions"
    __table_args__ = (Index("ix_candidate_sessions_candidate_id", "candidate_id"),)

    token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )

