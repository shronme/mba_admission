from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import ChatThreadStatus, MessageRole
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ChatThread(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "chat_threads"
    __table_args__ = (Index("ix_chat_threads_candidate_id", "candidate_id"),)

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[ChatThreadStatus] = mapped_column(
        SQLEnum(ChatThreadStatus, name="chat_thread_status", native_enum=True),
        nullable=False,
        default=ChatThreadStatus.ACTIVE,
        insert_default=ChatThreadStatus.ACTIVE,
    )
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="chat_threads")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_thread_id", "thread_id"),
        Index("ix_chat_messages_thread_created", "thread_id", "created_at"),
    )

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(MessageRole, name="message_role", native_enum=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    thread: Mapped[ChatThread] = relationship(back_populates="messages")
