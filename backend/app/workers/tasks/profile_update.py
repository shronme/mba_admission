"""
Async Celery task: update candidate profile attributes from a processed document.

This task is chained from process_uploaded_document and runs after the
"file received" chat notification has already been posted — so it never
delays the candidate-facing acknowledgement.

Steps:
1. Load the UploadedFile (reads extracted_text from extra).
2. Load the current CandidateProfile attributes.
3. Run ProfileAttributeExtractor (DSPy) to extract relevant attribute updates.
4. Merge updates into the profile (overwrite=True so documents can enrich values).
5. Run ProfileAgent (DSPy) to check completeness and synthesize derived attributes.
6. Persist the profile_complete flag.
7. If the profile just became complete, post a follow-up chat message to notify
   the candidate that the research agent will now take over.
"""

from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.sync_db import sync_session_scope
from app.db.enums import ChatThreadStatus, MessageRole
from app.db.models.candidate import CandidateProfile
from app.db.models.chat import ChatMessage, ChatThread
from app.db.models.files import UploadedFile
from app.db.enums import FileStatus

logger = logging.getLogger(__name__)


def _post_profile_complete_notification(candidate_id: uuid.UUID) -> None:
    """Post a chat message informing the candidate their profile is now complete."""
    content = (
        "Great news — your profile is now complete! "
        "I've reviewed everything you've shared and your background documents. "
        "The research agent will now take over to analyse school fit, "
        "build your shortlist, and map out your application strategy. "
        "You'll hear from us shortly with next steps."
    )
    with sync_session_scope() as session:
        result = session.execute(
            select(ChatThread)
            .where(ChatThread.candidate_id == candidate_id)
            .where(ChatThread.status == ChatThreadStatus.ACTIVE)
            .order_by(ChatThread.created_at.desc())
            .limit(1)
        )
        thread = result.scalar_one_or_none()
        if thread is None:
            logger.info(
                "profile_update no_active_thread candidate_id=%s — skipping completion notification",
                candidate_id,
            )
            return
        session.add(
            ChatMessage(
                thread_id=thread.id,
                role=MessageRole.ASSISTANT,
                content=content,
            )
        )
    logger.info(
        "profile_update completion_notification_posted candidate_id=%s thread_id=%s",
        candidate_id,
        thread.id,
    )


@celery_app.task(
    bind=True,
    name="app.jobs.update_profile_from_document",
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_kwargs={"max_retries": 3, "countdown": 15},
    retry_backoff=True,
    retry_jitter=True,
)
def update_profile_from_document(self, file_id: str) -> dict:
    file_uuid = uuid.UUID(file_id)
    logger.info(
        "profile_update start file_id=%s retries=%s", file_id, self.request.retries
    )

    use_openai = (
        (os.getenv("DSPY_MODE") or "mock").lower() == "openai"
        and bool(os.getenv("OPENAI_API_KEY"))
    )

    # --- 1. Load file record ---
    with sync_session_scope() as session:
        file_row = session.get(UploadedFile, file_uuid)
        if file_row is None:
            logger.error("profile_update file_not_found file_id=%s", file_id)
            return {"status": "skipped", "reason": "not_found"}

        if file_row.status != FileStatus.READY:
            logger.warning(
                "profile_update file_not_ready file_id=%s status=%s", file_id, file_row.status
            )
            return {"status": "skipped", "reason": "not_ready"}

        extracted_text: str | None = None
        if isinstance(file_row.extra, dict):
            extracted_text = file_row.extra.get("extracted_text")

        if not extracted_text:
            logger.info("profile_update no_extracted_text file_id=%s — skipping", file_id)
            return {"status": "skipped", "reason": "no_text"}

        candidate_id: uuid.UUID = file_row.candidate_id
        doc_type_value: str = (
            file_row.document_type.value if file_row.document_type else "unclassified"
        )

    # --- 2. Load current profile attributes ---
    with sync_session_scope() as session:
        result = session.execute(
            select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id)
        )
        profile_row = result.scalar_one_or_none()
        current_attributes: dict = profile_row.attributes or {} if profile_row else {}
        was_complete: bool = profile_row.profile_complete if profile_row else False

    if was_complete:
        logger.info(
            "profile_update already_complete candidate_id=%s — skipping", candidate_id
        )
        return {"status": "skipped", "reason": "already_complete"}

    # --- 3. Extract attribute updates from document ---
    from app.dspy.profile_attribute_extractor import run_profile_attribute_extractor

    attribute_updates = run_profile_attribute_extractor(
        document_text=extracted_text,
        document_type=doc_type_value,
        current_attributes=current_attributes,
        use_openai=use_openai,
    )
    logger.info(
        "profile_update extracted_attrs file_id=%s keys=%s",
        file_id,
        list(attribute_updates.keys()),
    )

    if not attribute_updates:
        logger.info("profile_update no_attr_updates file_id=%s — skipping merge", file_id)
        return {"status": "ok", "updates": 0}

    # --- 4. Merge updates into profile (documents can overwrite existing values) ---
    merged_attributes = {**current_attributes, **attribute_updates}

    with sync_session_scope() as session:
        result = session.execute(
            select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id)
        )
        profile_row = result.scalar_one_or_none()
        if profile_row is None:
            profile_row = CandidateProfile(candidate_id=candidate_id, attributes={})
            session.add(profile_row)

        profile_row.attributes = merged_attributes

    logger.info(
        "profile_update merged candidate_id=%s keys=%s",
        candidate_id,
        list(attribute_updates.keys()),
    )

    # --- 5. Run ProfileAgent to check completeness + synthesize derived attrs ---
    from app.dspy.profile_agent import run_profile_agent

    is_complete, gaps, synthesized, score = run_profile_agent(
        merged_attributes, use_openai=use_openai
    )
    logger.info(
        "profile_update profile_agent candidate_id=%s is_complete=%s gaps=%s",
        candidate_id,
        is_complete,
        gaps,
    )

    # Persist synthesized derived attributes alongside the flag.
    final_attributes = {**merged_attributes, **(synthesized or {})}

    # --- 6. Persist profile_complete flag, quality score, and synthesized attrs ---
    with sync_session_scope() as session:
        result = session.execute(
            select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id)
        )
        profile_row = result.scalar_one_or_none()
        if profile_row is not None:
            profile_row.attributes = final_attributes
            profile_row.profile_complete = is_complete
            profile_row.completeness_score = max(0, min(100, score))

    # --- 7. Notify the candidate if the profile just became complete ---
    if is_complete and not was_complete:
        _post_profile_complete_notification(candidate_id)

    logger.info(
        "profile_update done file_id=%s candidate_id=%s is_complete=%s",
        file_id,
        candidate_id,
        is_complete,
    )
    return {
        "status": "ok",
        "file_id": file_id,
        "updates": len(attribute_updates),
        "is_complete": is_complete,
    }
