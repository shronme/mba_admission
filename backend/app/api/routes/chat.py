from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from opentelemetry import trace as otel_trace
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_candidate_id_from_bearer_token
from app.core.db import get_db_session
from app.db.enums import ChatThreadStatus, FileStatus, MessageRole
from app.db.models.chat import ChatMessage, ChatThread
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.files import UploadedFile
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.chat_repo import ChatRepository
from app.dspy.pipeline import generate_assistant_response, generate_initial_greeting

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger(__name__)
tracer = otel_trace.get_tracer(__name__)


async def _retrieve_doc_snippets(
    *,
    session: AsyncSession,
    candidate_id: UUID,
    user_message: str,
) -> list[str]:
    """
    Return relevant document snippets for the given user message.

    Uses pgvector semantic search when OPENAI_API_KEY is available; falls back
    to naive full-text injection (up to 3 documents' extracted_text) otherwise.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import AsyncOpenAI
            from app.core.vector_store import search_async

            client = AsyncOpenAI(api_key=api_key)
            resp = await client.embeddings.create(
                model="text-embedding-3-small", input=user_message
            )
            query_embedding = resp.data[0].embedding
            snippets = await search_async(
                session, candidate_id=candidate_id, query_embedding=query_embedding
            )
            logger.debug(
                "chat_rag_search candidate_id=%s snippets=%s", candidate_id, len(snippets)
            )
            return snippets
        except Exception:
            logger.exception(
                "chat_rag_search_failed candidate_id=%s — falling back to naive injection",
                candidate_id,
            )

    # Fallback: inject raw extracted_text from up to 3 READY files.
    docs_result = await session.execute(
        select(UploadedFile)
        .where(UploadedFile.candidate_id == candidate_id)
        .where(UploadedFile.status == FileStatus.READY)
        .limit(3)
    )
    snippets = []
    for d in docs_result.scalars().all():
        if isinstance(d.extra, dict) and isinstance(d.extra.get("extracted_text"), str):
            snippets.append(d.extra["extracted_text"])
    return snippets


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
    # Load candidate + user + profile so the greeting can resume from where they left off.
    from sqlalchemy.orm import selectinload
    candidate = (
        await session.execute(
            select(Candidate)
            .options(selectinload(Candidate.user))
            .where(Candidate.id == candidate_id)
        )
    ).scalar_one()
    profile = (
        await session.execute(
            select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id)
        )
    ).scalar_one_or_none()
    file_count_res = await session.execute(
        select(func.count(UploadedFile.id))
        .where(UploadedFile.candidate_id == candidate_id)
        .where(UploadedFile.status == FileStatus.READY)
    )
    greeting_file_count = int(file_count_res.scalar_one() or 0)

    # Initial assistant message — personalised to existing profile progress.
    greeting_profile_complete = bool(profile.profile_complete) if profile else False
    initial, _ = generate_initial_greeting(
        candidate_name=candidate.user.full_name,
        existing_attributes=profile.attributes if profile else None,
        has_files=greeting_file_count > 0,
        profile_complete=greeting_profile_complete,
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
    from sqlalchemy.orm import selectinload as _sil
    candidate = (
        await session.execute(
            select(Candidate).options(_sil(Candidate.user)).where(Candidate.id == candidate_id)
        )
    ).scalar_one()
    profile = (await session.execute(select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id))).scalar_one_or_none()
    profile_complete: bool = bool(profile.profile_complete) if profile is not None else False
    candidate_profile: dict[str, Any] = {
        "full_name": candidate.user.full_name,
        "attributes": profile.attributes if profile is not None else None,
    }

    docs_snippets: list[str] = await _retrieve_doc_snippets(
        session=session,
        candidate_id=candidate_id,
        user_message=body.content,
    )

    recent_result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    recent_messages_raw = list(recent_result.scalars().all())
    recent_messages = [
        {
            "role": m.role.value if hasattr(m.role, "value") else str(m.role),
            "content": m.content,
            "extra": m.extra or {},
        }
        for m in reversed(recent_messages_raw)
        if m.content
    ]

    with tracer.start_as_current_span(
        "chat.pipeline",
        attributes={
            "openinference.span.kind": "CHAIN",
            "user.id": str(candidate_id),
            "session.id": str(thread_id),
        },
    ):
        full_text, profile_updates, is_now_complete, new_score = generate_assistant_response(
            user_message=body.content,
            file_count=file_count,
            candidate_profile=candidate_profile,
            docs_snippets=docs_snippets,
            recent_messages=recent_messages,
            profile_complete=profile_complete,
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

            # Persist extracted profile updates, completeness flag, and quality score (best-effort).
            score_changed = new_score >= 0  # -1 sentinel means no re-evaluation happened
            if profile_updates or (is_now_complete and not profile_complete) or score_changed:
                try:
                    candidate_repo = CandidateRepository(session)
                    if profile_updates:
                        await candidate_repo.merge_profile_attributes(candidate_id, profile_updates)
                    if is_now_complete or score_changed:
                        await candidate_repo.set_profile_complete(
                            candidate_id,
                            complete=is_now_complete,
                            score=new_score if score_changed else None,
                        )
                    await session.commit()
                    logger.info(
                        "chat_profile_updated candidate_id=%s keys=%s is_complete=%s score=%s",
                        candidate_id,
                        list(profile_updates.keys()),
                        is_now_complete,
                        new_score,
                    )
                except Exception:
                    logger.exception(
                        "chat_profile_update_failed candidate_id=%s", candidate_id
                    )

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

