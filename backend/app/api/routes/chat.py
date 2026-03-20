from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_candidate_id_from_bearer_token
from app.core.db import get_db_session
from app.db.enums import ChatThreadStatus, FileStatus, MessageRole
from app.db.models.chat import ChatMessage, ChatThread
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.files import UploadedFile
from app.repositories.chat_repo import ChatRepository
from app.dspy.pipeline import generate_assistant_response

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger(__name__)


class ChatStreamRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=50_000)


def _message_to_dict(m: ChatMessage) -> dict[str, Any]:
    role = m.role.value if hasattr(m.role, "value") else str(m.role)
    return {
        "id": str(m.id),
        "thread_id": str(m.thread_id),
        "role": role,
        "content": m.content,
        "created_at": m.created_at.isoformat() if getattr(m, "created_at", None) else None,
    }


async def _ensure_thread_owned(
    *,
    session: AsyncSession,
    candidate_id: UUID,
    thread_id: UUID,
) -> ChatThread:
    thread = await session.get(ChatThread, thread_id)
    if thread is None or thread.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="Thread not found") from None
    return thread


def _guardrail_off_topic(user_text: str) -> bool:
    t = user_text.lower()
    # Simple MVP guardrails; replace with DSPy-based classification later.
    if any(
        kw in t
        for kw in (
            "write my personal statement",
            "write the essay",
            "write an essay",
            "draft a full essay",
            "complete the essay",
        )
    ):
        return False  # not off-topic; it's a disallowed request we handle separately
    if any(kw in t for kw in ("calculus", "photosynthesis", "quantum", "chemistry")):
        return True
    return False


def _guardrail_disallowed_full_essay(user_text: str) -> bool:
    t = user_text.lower()
    return any(
        kw in t
        for kw in (
            "write my personal statement",
            "write the essay",
            "write an essay",
            "draft a full essay",
            "complete the essay",
        )
    )


def _stage_based_assistant_text(*, file_count: int, user_text: str) -> str:
    if _guardrail_disallowed_full_essay(user_text):
        return (
            "I can help you brainstorm, outline, and improve your draft, but I can’t write a full essay for you. "
            "If you paste the prompt and share 2-3 bullet points from your own story, I’ll help structure a strong outline."
        )

    if _guardrail_off_topic(user_text):
        return (
            "I can only help with graduate admissions (e.g., documents, goals, school strategy, and essay planning). "
            "Tell me what program/cycle you’re targeting and what documents you have."
        )

    if file_count <= 0:
        return (
            "Great — to get started, please upload any relevant documents you have (life story notes, grades/transcripts, resume, "
            "recommendations, or anything you think shows your background). After uploading, tell me your top US grad goals: "
            "which schools (or types), your target timeline/round, and the main story you want to be known for."
        )

    return (
        "Thanks for the documents. Now, tell me your Grad school goals for a top US university: \n"
        "1) Target schools (or MBA/MA/other + any names)\n"
        "2) Your timeline (application cycle and preferred round)\n"
        "3) 2-3 themes you want your application to communicate (leadership, impact, craft)\n"
        "4) Any constraints (work schedule, GPA range, test plan)\n\n"
        "Then I’ll propose a personalized roadmap and next steps."
    )


@router.post("/threads", response_model=None)
async def create_thread(
    candidate_id: UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    chat_repo = ChatRepository(session)

    thread = await chat_repo.create_thread(
        candidate_id=candidate_id,
        title="Admissions intake",
        status=ChatThreadStatus.ACTIVE,
        extra={"stage": "intake"},
    )
    # Initial assistant message for intake (DSPy pipeline driven).
    initial = generate_assistant_response(
        user_message="start intake",
        file_count=0,
        candidate_profile=None,
        docs_snippets=[],
        recent_messages=[],
    )
    await chat_repo.add_message(
        thread.id,
        role=MessageRole.ASSISTANT,
        content=initial,
        extra={"stage": "intake"},
    )
    await session.commit()
    logger.info("chat_thread_created candidate_id=%s thread_id=%s", candidate_id, thread.id)
    return {"thread_id": str(thread.id)}


@router.get("/threads/{thread_id}/messages", response_model=None)
async def list_thread_messages(
    thread_id: UUID,
    candidate_id: UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_thread_owned(
        session=session,
        candidate_id=candidate_id,
        thread_id=thread_id,
    )

    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc()),
    )
    messages = list(result.scalars().all())
    logger.info(
        "chat_thread_messages_list candidate_id=%s thread_id=%s count=%s",
        candidate_id,
        thread_id,
        len(messages),
    )
    return {"messages": [_message_to_dict(m) for m in messages]}


@router.post("/threads/{thread_id}/messages/stream", response_model=None)
async def stream_assistant_response(
    thread_id: UUID,
    body: ChatStreamRequest,
    candidate_id: UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    # Ensure thread is owned.
    await _ensure_thread_owned(
        session=session,
        candidate_id=candidate_id,
        thread_id=thread_id,
    )

    chat_repo = ChatRepository(session)

    # Persist user message immediately.
    await chat_repo.add_message(
        thread_id,
        role=MessageRole.USER,
        content=body.content,
    )
    # Placeholder assistant message (filled after streaming).
    assistant_msg = await chat_repo.add_message(
        thread_id,
        role=MessageRole.ASSISTANT,
        content="",
    )
    await session.commit()

    logger.info(
        "chat_stream_start candidate_id=%s thread_id=%s user_message_chars=%s",
        candidate_id,
        thread_id,
        len(body.content or ""),
    )

    # Determine "stage" (MVP heuristic for now).
    res = await session.execute(
        select(func.count(UploadedFile.id))
        .where(UploadedFile.candidate_id == candidate_id)
        .where(UploadedFile.status == FileStatus.READY),
    )
    file_count = int(res.scalar_one() or 0)

    # Memory / context injection (MVP): candidate profile + extracted doc snippets + recent messages.
    candidate = (await session.execute(select(Candidate).where(Candidate.id == candidate_id))).scalar_one()
    profile = (await session.execute(select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id))).scalar_one_or_none()
    candidate_profile: dict[str, Any] = {
        "full_name": candidate.full_name,
        "attributes": profile.attributes if profile is not None else None,
    }

    docs_result = await session.execute(
        select(UploadedFile).where(UploadedFile.candidate_id == candidate_id).where(UploadedFile.status == FileStatus.READY)
    )
    docs = list(docs_result.scalars().all())
    docs_snippets: list[str] = []
    for d in docs:
        if isinstance(d.extra, dict) and isinstance(d.extra.get("extracted_text"), str):
            docs_snippets.append(d.extra["extracted_text"])
        if len(docs_snippets) >= 3:
            break

    recent_result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    recent_messages_raw = list(recent_result.scalars().all())
    recent_messages = [
        {"role": m.role.value if hasattr(m.role, "value") else str(m.role), "content": m.content}
        for m in reversed(recent_messages_raw)
        if m.content
    ]

    full_text = generate_assistant_response(
        user_message=body.content,
        file_count=file_count,
        candidate_profile=candidate_profile,
        docs_snippets=docs_snippets,
        recent_messages=recent_messages,
    )

    async def gen() -> AsyncGenerator[str, None]:
        nonlocal full_text
        try:
            # Stream by tokens (here: whitespace-preserving chunks).
            words = full_text.split(" ")
            acc = ""
            for i, w in enumerate(words):
                # Re-add spaces lost by split.
                chunk = w + ("" if i == len(words) - 1 else " ")
                acc += chunk
                yield chunk
                await asyncio.sleep(0.01)

            assistant_msg.content = acc
            session.add(assistant_msg)
            await session.commit()
            logger.info("chat_stream_complete candidate_id=%s thread_id=%s", candidate_id, thread_id)
        except Exception:
            logger.exception(
                "chat_stream_generator_failed candidate_id=%s thread_id=%s",
                candidate_id,
                thread_id,
            )
            # Best-effort persist error marker so the UI/debugger can see it.
            try:
                assistant_msg.content = assistant_msg.content or "Sorry, something went wrong."
                session.add(assistant_msg)
                await session.commit()
            except Exception:
                logger.exception(
                    "chat_stream_generator_failed_persist candidate_id=%s thread_id=%s",
                    candidate_id,
                    thread_id,
                )
            raise

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")

