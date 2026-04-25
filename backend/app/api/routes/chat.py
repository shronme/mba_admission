from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import re
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.dspy.school_advisor import generate_opening_advisor_message
from app.dspy.profile_language_normalize import run_profile_attributes_english_normalize

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger(__name__)
app_logger = logging.getLogger("app")
tracer = otel_trace.get_tracer(__name__)


async def _retrieve_doc_snippets(
    *,
    session: AsyncSession,
    candidate_id: UUID,
    user_message: str,
) -> list[str]:
    """
    Return relevant document snippets for the given user message.

    When `OPENAI_API_KEY` is set, this uses semantic top-k retrieval via
    embeddings + pgvector search. If embeddings are unavailable or retrieval
    fails, it falls back to a legacy naive injection of extracted full text
    from recent processed uploads.
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

    # Fallback: inject raw extracted_text from up to 3 processed files (ready or still in review).
    docs_result = await session.execute(
        select(UploadedFile)
        .where(UploadedFile.candidate_id == candidate_id)
        .where(UploadedFile.status.in_((FileStatus.READY, FileStatus.REVIEWING)))
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
        "extra": m.extra or {},
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


def _profile_selected_schools(attrs: dict[str, Any]) -> list[dict[str, Any]] | None:
    raw = attrs.get("selected_schools")
    if not isinstance(raw, list):
        return None
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        school = row.get("school")
        program_slug = row.get("program_slug")
        if not isinstance(school, str) or not school.strip():
            continue
        if not isinstance(program_slug, str) or not program_slug.strip():
            continue
        out.append(
            {
                "school": school.strip(),
                "program_slug": program_slug.strip(),
                "program_display_name": row.get("program_display_name"),
            }
        )
    return out or None


@router.post("/advisor-threads", response_model=None)
async def create_or_get_advisor_thread(
    new: bool = Query(default=False),
    candidate_id: UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Create or retrieve an advisor-stage chat thread.

    - Default: return existing active advisor thread if present; else create.
    - new=true: archive existing active advisor thread(s) and create a new one.
    """
    from app.core.dspy_runtime import openai_calls_enabled

    # Load profile attributes and enforce selection prerequisite.
    prof = (
        await session.execute(
            select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id),
        )
    ).scalar_one_or_none()
    attrs = dict(prof.attributes or {}) if prof else {}
    selected = _profile_selected_schools(attrs)
    if not selected:
        raise HTTPException(
            status_code=409,
            detail="Confirm at least one school before starting the advisor.",
        )

    chat_repo = ChatRepository(session)

    # Find existing active advisor thread(s).
    active_advisor = await chat_repo.get_latest_active_thread_by_stage(
        candidate_id, stage="advisor"
    )

    if active_advisor is not None and not new:
        return {"thread_id": str(active_advisor.id), "is_new": False}

    # If new=True, archive any existing advisor threads.
    if new:
        threads = await chat_repo.list_threads_for_candidate(candidate_id)
        for t in threads:
            if t.status != ChatThreadStatus.ACTIVE:
                continue
            if not (isinstance(t.extra, dict) and t.extra.get("stage") == "advisor"):
                continue
            t.status = ChatThreadStatus.ARCHIVED
            session.add(t)
        await session.commit()

    # Create fresh advisor thread.
    thread = await chat_repo.create_thread(
        candidate_id=candidate_id,
        title="School advisor",
        status=ChatThreadStatus.ACTIVE,
        extra={"stage": "advisor", "selected_schools": selected},
    )

    # Personalised opening assistant message.
    from sqlalchemy.orm import selectinload

    candidate = (
        await session.execute(
            select(Candidate)
            .options(selectinload(Candidate.user))
            .where(Candidate.id == candidate_id)
        )
    ).scalar_one()
    opening = generate_opening_advisor_message(
        selected_schools=selected,
        admission_evaluation_result=attrs.get("admission_evaluation_result")
        if isinstance(attrs.get("admission_evaluation_result"), dict)
        else None,
        candidate_name=candidate.user.full_name,
        use_openai=openai_calls_enabled(),
    )
    await chat_repo.add_message(
        thread.id,
        role=MessageRole.ASSISTANT,
        content=opening,
        extra={"stage": "advisor"},
    )
    await session.commit()
    return {"thread_id": str(thread.id), "is_new": True}


@router.post("/threads", response_model=None)
async def create_thread(
    candidate_id: UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    # Reuse the latest active thread when one exists so the UI matches
    # `_post_chat_notification` in document_processing (same ordering), avoiding
    # orphan threads from remounts / Strict Mode and missing upload messages.
    existing = (
        await session.execute(
            select(ChatThread)
            .where(ChatThread.candidate_id == candidate_id)
            .where(ChatThread.status == ChatThreadStatus.ACTIVE)
            .order_by(ChatThread.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        logger.info(
            "chat_thread_reused candidate_id=%s thread_id=%s",
            candidate_id,
            existing.id,
        )
        return {"thread_id": str(existing.id)}

    chat_repo = ChatRepository(session)

    existing = await chat_repo.get_latest_active_thread(candidate_id)
    if existing is not None:
        logger.info(
            "chat_thread_reused candidate_id=%s thread_id=%s",
            candidate_id,
            existing.id,
        )
        return {"thread_id": str(existing.id)}

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
        .where(UploadedFile.status.in_((FileStatus.READY, FileStatus.REVIEWING)))
    )
    greeting_file_count = int(file_count_res.scalar_one() or 0)

    # Initial assistant message — personalised to existing profile progress.
    greeting_profile_complete = bool(profile.profile_complete) if profile else False
    initial, _ = generate_initial_greeting(
        candidate_name=candidate.user.full_name,
        existing_attributes=profile.attributes if profile else None,
        has_files=greeting_file_count > 0,
        profile_complete=greeting_profile_complete,
        program_type=candidate.program_type,
        grad_program_focus=profile.grad_program_focus if profile else None,
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
    thread = await _ensure_thread_owned(
        session=session,
        candidate_id=candidate_id,
        thread_id=thread_id,
    )

    chat_repo = ChatRepository(session)

    # Persist the user message in its own transaction so it gets an earlier
    # created_at than the assistant placeholder. Both use server_default=func.now()
    # which returns the PostgreSQL transaction start time — committing them together
    # would give them identical timestamps and cause non-deterministic ordering.
    await chat_repo.add_message(
        thread_id,
        role=MessageRole.USER,
        content=body.content,
    )
    await session.commit()

    # Placeholder assistant message (content filled at end of streaming).
    assistant_msg = await chat_repo.add_message(
        thread_id,
        role=MessageRole.ASSISTANT,
        content="",
    )
    await session.commit()

    app_logger.info(
        "chat_stream_start candidate_id=%s thread_id=%s user_message_chars=%s",
        candidate_id,
        thread_id,
        len(body.content or ""),
    )

    # Determine "stage" (MVP heuristic for now).
    res = await session.execute(
        select(UploadedFile.id, UploadedFile.document_type, UploadedFile.original_filename)
        .where(UploadedFile.candidate_id == candidate_id)
        .where(UploadedFile.status.in_((FileStatus.READY, FileStatus.REVIEWING))),
    )
    uploaded_rows = list(res.all())
    file_count = len(uploaded_rows)
    # Summarize uploaded documents so the advisor agent knows what content is
    # already indexed and retrievable via `retrieve_candidate_context`. This
    # prevents the agent from asking the candidate to paste content they've
    # already uploaded (e.g. "please paste your CV").
    available_documents: list[dict[str, Any]] = []
    for _id, doc_type, filename in uploaded_rows:
        available_documents.append(
            {
                "document_type": (
                    doc_type.value
                    if hasattr(doc_type, "value")
                    else (str(doc_type) if doc_type is not None else "unclassified")
                ),
                "original_filename": filename,
            }
        )

    # Memory / context injection (MVP): candidate profile + extracted doc snippets + recent messages.
    from sqlalchemy.orm import selectinload as _sil
    candidate = (
        await session.execute(
            select(Candidate).options(_sil(Candidate.user)).where(Candidate.id == candidate_id)
        )
    ).scalar_one()
    profile = (await session.execute(select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id))).scalar_one_or_none()

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

    # Refresh the profile object so we pick up any completeness updates that the
    # Celery extraction task may have committed concurrently since the initial load.
    # Without this, a candidate's turn that starts while Celery is still running
    # sees a stale profile_complete=False and incorrectly routes to IntakeInterviewer.
    if profile is not None:
        await session.refresh(profile)
    profile_complete: bool = bool(profile.profile_complete) if profile is not None else False
    stored_completeness_score: int = int(profile.completeness_score) if profile is not None else 0
    candidate_profile: dict[str, Any] = {
        "full_name": candidate.user.full_name,
        "attributes": profile.attributes if profile is not None else None,
    }
    thread_stage = None
    thread_selected_schools = None
    if isinstance(thread.extra, dict):
        thread_stage = str(thread.extra.get("stage") or "") or None
        if thread_stage == "advisor":
            raw = thread.extra.get("selected_schools")
            if isinstance(raw, list):
                thread_selected_schools = [r for r in raw if isinstance(r, dict)]
    admission_result = None
    if profile is not None and isinstance(profile.attributes, dict):
        raw_res = profile.attributes.get("admission_evaluation_result")
        if isinstance(raw_res, dict):
            admission_result = raw_res

    with tracer.start_as_current_span(
        "chat.pipeline",
        attributes={
            "openinference.span.kind": "CHAIN",
            "user.id": str(candidate_id),
            "session.id": str(thread_id),
        },
    ):
        gen_out: Any | None = None
        full_text, profile_updates, is_now_complete, new_score = "", {}, True, 100

        if (thread_stage or "").lower() != "advisor":
            gen_out = await generate_assistant_response(
                user_message=body.content,
                file_count=file_count,
                candidate_profile=candidate_profile,
                docs_snippets=docs_snippets,
                recent_messages=recent_messages,
                profile_complete=profile_complete,
                current_completeness_score=stored_completeness_score,
                thread_stage=thread_stage,
                selected_schools=thread_selected_schools,
                admission_evaluation_result=admission_result,
                session=session,
                candidate_id=candidate_id,
                openai_client=None,
                available_documents=available_documents,
            )
            full_text, profile_updates, is_now_complete, new_score = gen_out

    def _extract_artifact_event(pred: Any, response_text: str | None = None) -> dict[str, Any] | None:
        artifact_id = getattr(pred, "artifact_id", None)
        artifact_type = getattr(pred, "artifact_type", None)

        artifact_json: dict[str, Any] | None = None
        traj = getattr(pred, "trajectory", None)
        if traj:
            # Best-effort: scan trajectory for a JSON dict containing artifact fields.
            for step in reversed(list(traj)):
                val = None
                if isinstance(step, dict):
                    val = step.get("observation") or step.get("result") or step.get("output")
                elif isinstance(step, str):
                    val = step
                if not isinstance(val, str):
                    continue
                val_s = val.strip()
                if not (val_s.startswith("{") and val_s.endswith("}")):
                    continue
                try:
                    parsed = json.loads(val_s)
                except Exception:
                    continue
                if isinstance(parsed, dict) and "artifact_id" in parsed and "download_url" in parsed:
                    artifact_json = parsed
                    break

        # If the prediction directly includes artifact fields, use those. Otherwise fall back to tool json.
        if artifact_json:
            return {
                "type": "artifact",
                "artifact_id": str(artifact_json.get("artifact_id") or ""),
                "artifact_type": str(artifact_json.get("artifact_type") or artifact_type or ""),
                "title": str(artifact_json.get("title") or ""),
                "school_name": str(artifact_json.get("school_name") or ""),
                "download_url": str(artifact_json.get("download_url") or ""),
            }

        # Fallback: if the model printed a download URL in the response text, extract it.
        if response_text:
            m = re.search(
                r"(/api)?/artifacts/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/download",
                response_text,
            )
            if m:
                extracted_id = m.group(2)
                # Normalize to the same-origin API proxy path for the browser.
                normalized_url = f"/api/artifacts/{extracted_id}/download"
                return {
                    "type": "artifact",
                    "artifact_id": extracted_id,
                    "artifact_type": str(artifact_type or ""),
                    "title": "",
                    "school_name": "",
                    "download_url": normalized_url,
                }

        if artifact_id:
            return {
                "type": "artifact",
                "artifact_id": str(artifact_id),
                "artifact_type": str(artifact_type or ""),
                "title": "",
                "school_name": "",
                "download_url": f"/api/artifacts/{artifact_id}/download",
            }
        return None

    async def gen() -> AsyncGenerator[str, None]:
        nonlocal full_text
        try:
            if (thread_stage or "").lower() == "advisor":
                # Advisor stage: NDJSON protocol
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    from openai import AsyncOpenAI

                    openai_client = AsyncOpenAI(api_key=api_key)
                else:
                    openai_client = object()

                pred = await generate_assistant_response(
                    user_message=body.content,
                    file_count=file_count,
                    candidate_profile=candidate_profile,
                    docs_snippets=docs_snippets,
                    recent_messages=recent_messages,
                    profile_complete=profile_complete,
                    current_completeness_score=stored_completeness_score,
                    thread_stage=thread_stage,
                    selected_schools=thread_selected_schools,
                    admission_evaluation_result=admission_result,
                    session=session,
                    candidate_id=candidate_id,
                    openai_client=openai_client,
                    available_documents=available_documents,
                )
                text = str(getattr(pred, "response", "") or "")
                full_text = text
                # Emit text (single chunk for now).
                if text:
                    yield json.dumps({"type": "text_chunk", "value": text}) + "\n"

                artifact_event = _extract_artifact_event(pred, response_text=text)
                if artifact_event and artifact_event.get("artifact_id"):
                    yield json.dumps(artifact_event) + "\n"

                assistant_msg.content = text
                session.add(assistant_msg)
                await session.commit()

                # Patch ChatMessage.extra with artifact fields after stream closes.
                if artifact_event and artifact_event.get("artifact_id"):
                    extra_patch = {
                        "artifact_id": artifact_event.get("artifact_id"),
                        "artifact_type": artifact_event.get("artifact_type"),
                        "title": artifact_event.get("title"),
                        "school_name": artifact_event.get("school_name"),
                        "download_url": artifact_event.get("download_url"),
                    }
                    try:
                        await chat_repo.patch_message_extra(assistant_msg.id, extra_patch)
                        await session.commit()
                    except Exception:
                        logger.exception(
                            "chat_message_extra_patch_failed candidate_id=%s message_id=%s",
                            candidate_id,
                            assistant_msg.id,
                        )
                app_logger.info(
                    "chat_stream_complete advisor candidate_id=%s thread_id=%s",
                    candidate_id,
                    thread_id,
                )
                return

            # Non-advisor stages: stream by tokens (whitespace-preserving chunks).
            words = full_text.split(" ")
            acc = ""
            for i, w in enumerate(words):
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
                        from app.core.dspy_runtime import openai_calls_enabled

                        use_openai_norm = openai_calls_enabled()
                        if use_openai_norm:
                            prof_row = (
                                await session.execute(
                                    select(CandidateProfile).where(
                                        CandidateProfile.candidate_id == candidate_id
                                    )
                                )
                            ).scalar_one_or_none()
                            if prof_row is not None:
                                attrs_before = dict(prof_row.attributes or {})
                                attrs_after = await asyncio.to_thread(
                                    functools.partial(
                                        run_profile_attributes_english_normalize,
                                        use_openai=True,
                                    ),
                                    attrs_before,
                                )
                                if attrs_after != attrs_before:
                                    prof_row.attributes = attrs_after
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

            app_logger.info(
                "chat_stream_complete candidate_id=%s thread_id=%s", candidate_id, thread_id
            )
        except Exception:
            logger.exception(
                "chat_stream_generator_failed candidate_id=%s thread_id=%s",
                candidate_id,
                thread_id,
            )
            if (thread_stage or "").lower() == "advisor":
                yield json.dumps(
                    {"type": "error", "message": "Sorry, something went wrong."}
                ) + "\n"
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
                return
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

    media_type = (
        "application/x-ndjson"
        if (thread_stage or "").lower() == "advisor"
        else "text/plain; charset=utf-8"
    )
    return StreamingResponse(gen(), media_type=media_type)

