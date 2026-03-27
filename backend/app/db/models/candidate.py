from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum as SQLEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import CandidateStage, CandidateStatus, ProgramType
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Candidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "candidates"
    __table_args__ = (
        Index("ix_candidates_status", "status"),
        Index("ix_candidates_program_type", "program_type"),
        UniqueConstraint("user_id", name="uq_candidates_user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    program_type: Mapped[ProgramType] = mapped_column(
        SQLEnum(ProgramType, name="program_type", native_enum=True),
        nullable=False,
        default=ProgramType.GRAD,
        insert_default=ProgramType.GRAD,
    )
    status: Mapped[CandidateStatus] = mapped_column(
        SQLEnum(CandidateStatus, name="candidate_status", native_enum=True),
        nullable=False,
        default=CandidateStatus.ACTIVE,
        insert_default=CandidateStatus.ACTIVE,
    )
    stage: Mapped[CandidateStage] = mapped_column(
        SQLEnum(CandidateStage, name="candidate_stage", native_enum=True),
        nullable=False,
        default=CandidateStage.INTAKE,
        insert_default=CandidateStage.INTAKE,
    )
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship(back_populates="candidate")  # type: ignore[name-defined]  # noqa: F821
    profile: Mapped[CandidateProfile | None] = relationship(
        back_populates="candidate",
        uselist=False,
        cascade="all, delete-orphan",
    )
    chat_threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    strategy_decisions: Mapped[list["StrategyDecision"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    task_items: Mapped[list["TaskItem"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    essay_drafts: Mapped[list["EssayDraft"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    ai_runs: Mapped[list["AiRun"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class CandidateProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "candidate_profiles"
    __table_args__ = (UniqueConstraint("candidate_id", name="uq_candidate_profiles_candidate_id"),)

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    headline: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    profile_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, insert_default=False
    )
    completeness_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, insert_default=0
    )
    country_of_residence: Mapped[str | None] = mapped_column(String(128), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    intake_form_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, insert_default=False
    )
    grad_program_focus: Mapped[str | None] = mapped_column(String(128), nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="profile")
