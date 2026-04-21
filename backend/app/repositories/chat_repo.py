from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import cast, func
from sqlalchemy.orm import selectinload

from app.db.enums import ChatThreadStatus, MessageRole
from app.db.models.chat import ChatMessage, ChatThread
from app.repositories.base import BaseRepository


class ChatRepository(BaseRepository):
    async def create_thread(
        self,
        candidate_id: uuid.UUID,
        *,
        title: str | None = None,
        status: ChatThreadStatus = ChatThreadStatus.ACTIVE,
        extra: dict | None = None,
    ) -> ChatThread:
        thread = ChatThread(
            candidate_id=candidate_id,
            title=title,
            status=status,
            extra=extra,
        )
        self.session.add(thread)
        await self.session.flush()
        return thread

    async def add_message(
        self,
        thread_id: uuid.UUID,
        *,
        role: MessageRole,
        content: str,
        extra: dict | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            thread_id=thread_id,
            role=role,
            content=content,
            extra=extra,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def get_latest_active_thread(self, candidate_id: uuid.UUID) -> ChatThread | None:
        """Most recent active thread — same selection workers use for file notifications."""
        result = await self.session.execute(
            select(ChatThread)
            .where(ChatThread.candidate_id == candidate_id)
            .where(ChatThread.status == ChatThreadStatus.ACTIVE)
            .order_by(ChatThread.created_at.desc())
            .limit(1),
        )
        return result.scalar_one_or_none()

    async def list_threads_for_candidate(self, candidate_id: uuid.UUID) -> list[ChatThread]:
        result = await self.session.execute(
            select(ChatThread)
            .where(ChatThread.candidate_id == candidate_id)
            .order_by(ChatThread.created_at.desc()),
        )
        return list(result.scalars().all())

    async def get_latest_active_thread_by_stage(
        self,
        candidate_id: uuid.UUID,
        *,
        stage: str,
    ) -> ChatThread | None:
        """
        Most recent active thread where `thread.extra.stage` matches.

        Note: extra is JSONB so filtering is done in Python to keep this repo
        SQLAlchemy-only and avoid JSON dialect differences for now.
        """
        threads = await self.list_threads_for_candidate(candidate_id)
        for t in threads:
            if t.status != ChatThreadStatus.ACTIVE:
                continue
            if isinstance(t.extra, dict) and str(t.extra.get("stage") or "") == stage:
                return t
        return None

    async def get_thread_with_messages(self, thread_id: uuid.UUID) -> ChatThread | None:
        result = await self.session.execute(
            select(ChatThread)
            .options(selectinload(ChatThread.messages))
            .where(ChatThread.id == thread_id),
        )
        return result.scalar_one_or_none()

    async def patch_message_extra(self, message_id: uuid.UUID, extra_patch: dict) -> None:
        """
        JSONB merge-patch of ChatMessage.extra (preserves existing keys).
        """
        if not extra_patch:
            return
        await self.session.execute(
            update(ChatMessage)
            .where(ChatMessage.id == message_id)
            .values(
                extra=func.coalesce(ChatMessage.extra, cast({}, JSONB)).op("||")(
                    cast(extra_patch, JSONB)
                )
            )
        )
        await self.session.flush()
