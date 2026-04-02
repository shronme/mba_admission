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
5. When OpenAI mode is on, normalize merged text attributes to English (post-merge).
6. Run ProfileAgent (DSPy) to check completeness and synthesize derived attributes.
7. Persist the profile_complete flag.
8. Post an extraction summary chat message so the candidate knows what was reviewed.
9. If the profile just became complete, post a follow-up completion notification.
"""

from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.sync_db import sync_session_scope
from app.db.models.candidate import CandidateProfile
from app.db.models.files import UploadedFile
from app.db.enums import FileStatus

logger = logging.getLogger(__name__)

_PROFILE_UPDATE_ELIGIBLE = frozenset({FileStatus.REVIEWING, FileStatus.READY})


def _mark_file_ready(file_uuid: uuid.UUID) -> None:
    """Clear reviewing state so the UI and download API treat the file as fully processed."""
    with sync_session_scope() as session:
        row = session.get(UploadedFile, file_uuid)
        if row is None:
            return
        if row.status == FileStatus.REVIEWING:
            row.status = FileStatus.READY


def _post_chat_message(candidate_id: uuid.UUID, content: str, extra: dict | None = None) -> None:
    # Chat is deprecated/disabled. Keep as a no-op so task flow remains stable.
    logger.info(
        "profile_update chat_message_skipped candidate_id=%s chars=%s extra_keys=%s",
        candidate_id,
        len(content or ""),
        list((extra or {}).keys()),
    )


def _build_extraction_summary(
    doc_type: str,
    attribute_updates: dict,
    gaps: list[str],
) -> str:
    """
    Build a natural-language summary of what was extracted from the document.
    Does not include a follow-up question — that is posted as a separate message.
    """
    doc_label = {
        "cv": "CV",
        "resume": "CV",
        "life_story": "life story",
        "personal_statement": "personal statement",
        "recommendation_letter": "recommendation letter",
        "grade_sheet": "transcript",
    }.get(doc_type.lower().replace("-", "_"), "document")

    extracted_attrs = list(attribute_updates.keys())
    attr_labels = [k.replace("_", " ") for k in extracted_attrs]

    if attr_labels:
        if len(attr_labels) == 1:
            extracted_str = attr_labels[0]
        elif len(attr_labels) == 2:
            extracted_str = f"{attr_labels[0]} and {attr_labels[1]}"
        else:
            extracted_str = ", ".join(attr_labels[:-1]) + f", and {attr_labels[-1]}"
        extraction_line = (
            f"I've finished reviewing your {doc_label} and captured information about "
            f"your {extracted_str}."
        )
    else:
        extraction_line = f"I've finished reviewing your {doc_label}."

    if gaps:
        gap_count = len(gaps)
        remaining = "one area" if gap_count == 1 else f"{gap_count} areas"
        extraction_line += (
            f" There {'is' if gap_count == 1 else 'are'} {remaining} "
            "left to complete your profile."
        )

    return extraction_line


def _build_first_gap_question(gaps: list[str]) -> str | None:
    """
    Return a natural first gap-filling question for the highest-priority gap,
    or None if there are no gaps remaining.
    """
    if not gaps:
        return None

    from app.dspy.intake_interviewer import _MOCK_QUESTION_HINTS
    from app.dspy.profile_agent import PROFILE_ATTRIBUTE_SCHEMA

    first_gap = gaps[0]
    hint = _MOCK_QUESTION_HINTS.get(first_gap)
    if hint:
        gap_label = first_gap.replace("_", " ")
        return f"Let's start filling in the gaps. First up — {gap_label}: {hint}"

    schema_desc = PROFILE_ATTRIBUTE_SCHEMA.get(first_gap, "").split(".")[0]
    gap_label = first_gap.replace("_", " ")
    return f"Let me ask about your {gap_label}. {schema_desc}."


def _post_profile_complete_notification(candidate_id: uuid.UUID) -> None:
    """Post a chat message informing the candidate their profile is now complete."""
    content = (
        "Great news — your profile is now complete! "
        "I've reviewed everything you've shared and your background documents. "
        "The research agent will now take over to analyse school fit, "
        "build your shortlist, and map out your application strategy. "
        "You'll hear from us shortly with next steps."
    )
    _post_chat_message(candidate_id, content)


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

        if file_row.status not in _PROFILE_UPDATE_ELIGIBLE:
            logger.warning(
                "profile_update file_not_ready file_id=%s status=%s", file_id, file_row.status
            )
            return {"status": "skipped", "reason": "not_ready"}

        extracted_text: str | None = None
        if isinstance(file_row.extra, dict):
            extracted_text = file_row.extra.get("extracted_text")

        if not extracted_text:
            logger.info("profile_update no_extracted_text file_id=%s — skipping", file_id)
            _mark_file_ready(file_uuid)
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
        stored_score: int = int(profile_row.completeness_score) if profile_row else 0

    if was_complete:
        logger.info(
            "profile_update already_complete candidate_id=%s — skipping", candidate_id
        )
        _mark_file_ready(file_uuid)
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

    merged_attributes = {**current_attributes, **attribute_updates}

    # If doc extraction didn't yield a usable core_identity, run a focused, full-context
    # synthesis pass. This is especially important for CVs where "identity" is implicit
    # (roles/scope/impact) and can be missed by broad multi-attribute extraction.
    if not (merged_attributes.get("core_identity") or "").strip():
        try:
            from app.dspy.profile_attribute_synthesizer import run_single_attribute_synthesizer

            synthesized_core_identity = run_single_attribute_synthesizer(
                document_text=extracted_text,
                document_type=doc_type_value,
                current_attributes=merged_attributes,
                target_attribute_key="core_identity",
                use_openai=use_openai,
            )
            if synthesized_core_identity.strip():
                merged_attributes = {**merged_attributes, "core_identity": synthesized_core_identity.strip()}
                # Make sure the summary message reflects that we captured core_identity.
                if "core_identity" not in attribute_updates:
                    attribute_updates = {**attribute_updates, "core_identity": synthesized_core_identity.strip()}
        except Exception:
            logger.exception(
                "profile_update core_identity_synthesis_failed candidate_id=%s file_id=%s",
                candidate_id,
                file_id,
            )

    if attribute_updates and use_openai:
        from app.dspy.profile_language_normalize import run_profile_attributes_english_normalize

        merged_attributes = run_profile_attributes_english_normalize(
            merged_attributes, use_openai=True
        )

    # --- 4. Merge document fields into profile when the extractor found something new ---
    if attribute_updates:
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
    else:
        logger.info(
            "profile_update no_attr_updates file_id=%s — refreshing completeness only",
            file_id,
        )

    # --- 5. Run ProfileAgent to check completeness + synthesize derived attrs ---
    from app.dspy.profile_agent import run_profile_agent

    is_complete, gaps, synthesized, score = run_profile_agent(
        merged_attributes, use_openai=use_openai, min_score=stored_score
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
        if profile_row is None:
            profile_row = CandidateProfile(candidate_id=candidate_id, attributes={})
            session.add(profile_row)

        profile_row.attributes = final_attributes
        profile_row.profile_complete = is_complete
        profile_row.completeness_score = max(0, min(100, score))

    # --- 7. Post extraction summary + first gap question ---
    if not is_complete:
        summary = _build_extraction_summary(doc_type_value, attribute_updates, gaps)
        _post_chat_message(candidate_id, summary, extra={"type": "extraction_summary"})

        first_question = _build_first_gap_question(gaps)
        if first_question:
            _post_chat_message(candidate_id, first_question)

    # --- 8. Notify the candidate if the profile just became complete ---
    if is_complete and not was_complete:
        _post_profile_complete_notification(candidate_id)

    logger.info(
        "profile_update done file_id=%s candidate_id=%s is_complete=%s",
        file_id,
        candidate_id,
        is_complete,
    )
    _mark_file_ready(file_uuid)
    return {
        "status": "ok",
        "file_id": file_id,
        "updates": len(attribute_updates),
        "is_complete": is_complete,
    }
