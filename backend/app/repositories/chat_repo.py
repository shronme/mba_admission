from __future__ import annotations

import uuid

from sqlalchemy import select
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

    async def get_thread_with_messages(self, thread_id: uuid.UUID) -> ChatThread | None:
        result = await self.session.execute(
            select(ChatThread)
            .options(selectinload(ChatThread.messages))
            .where(ChatThread.id == thread_id),
        )
        return result.scalar_one_or_none()
