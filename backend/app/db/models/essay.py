from __future__ import annotations

import uuid

from sqlalchemy import Enum as SQLEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import EssayStatus, ReviewerType
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EssayDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "essay_drafts"
    __table_args__ = (Index("ix_essay_drafts_candidate_id", "candidate_id"),)

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EssayStatus] = mapped_column(
        SQLEnum(EssayStatus, name="essay_status", native_enum=True),
        nullable=False,
        default=EssayStatus.DRAFT,
        insert_default=EssayStatus.DRAFT,
    )
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="essay_drafts")
    reviews: Mapped[list["EssayReview"]] = relationship(
        back_populates="essay_draft",
        cascade="all, delete-orphan",
    )


class EssayReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "essay_reviews"
    __table_args__ = (Index("ix_essay_reviews_essay_draft_id", "essay_draft_id"),)

    essay_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("essay_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_type: Mapped[ReviewerType] = mapped_column(
        SQLEnum(ReviewerType, name="reviewer_type", native_enum=True),
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    essay_draft: Mapped[EssayDraft] = relationship(back_populates="reviews")
