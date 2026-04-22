from __future__ import annotations

import json
import logging
import time
import uuid
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func, select

from app.core.vector_store import search_async
from app.db.models.candidate import CandidateProfile
from app.db.models.knowledge_chunk import KnowledgeChunk
from app.repositories.cv_draft_repository import CVDraftRepository
from app.repositories.essay_draft_repository import EssayDraftRepository
from app.repositories.uploaded_file_repository import UploadedFileRepository

logger = logging.getLogger(__name__)

# Strict allow-list for `get_full_document`. Mirrors `DocumentType` but
# intentionally excludes `irrelevant` / `unclassified` per FR-2. Tuple order
# is the public display order used in the error string below.
_FULL_DOC_TYPES: tuple[str, ...] = (
    "cv",
    "life_story",
    "recommendation_letter",
    "grade_sheet",
)


def build_agent_tools(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    openai_client: Any,
) -> tuple[
    Callable[[str], Awaitable[str]],
    Callable[[str, str, str, str | None], Awaitable[str]],
    Callable[[str], Awaitable[str]],
    Callable[..., Awaitable[str]],
]:
    async def retrieve_candidate_context(query: str) -> str:
        """
        Retrieve relevant passages from the candidate's uploaded documents
        (CV, transcripts, recommendation letters, life story, etc.).

        Use this whenever the candidate's request depends on facts that are
        plausibly in their uploaded documents — for example, before improving
        a CV, reviewing an essay, summarizing experience, or answering
        questions about their background. DO NOT ask the candidate to paste
        content that could be fetched with this tool.

        Args:
            query: A natural-language description of what you need, e.g.
                "full CV work experience and education history" or
                "candidate leadership achievements and awards".

        Returns:
            A string containing the top matching passages from the candidate's
            documents, each prefixed with an index, or "No relevant context
            found." if nothing matched.
        """
        start = time.perf_counter()
        try:
            maybe = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query,
            )
            resp = await maybe if inspect.isawaitable(maybe) else maybe
            embedding = resp.data[0].embedding
            chunks = await search_async(
                session,
                candidate_id=candidate_id,
                query_embedding=embedding,
                top_k=8,
            )
            if not chunks:
                return "No relevant context found."
            return "\n\n".join(f"[{i+1}] {text}" for i, text in enumerate(chunks))
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "agent_tool name=retrieve_candidate_context query_len=%s duration_ms=%s",
                len(query or ""),
                elapsed_ms,
            )

    async def get_full_document(document_type: str) -> str:
        """
        Return the full `extracted_text` of the latest uploaded document of
        the requested type for this candidate.

        Prefer this tool over `retrieve_candidate_context` when you need the
        **complete** body of a specific document (e.g. for CV/life-story
        rewrites). `retrieve_candidate_context` returns ranked snippets — it
        may omit sections, formatting, or tail content.

        Args:
            document_type: One of "cv", "life_story", "recommendation_letter",
                "grade_sheet". Case-sensitive.

        Returns:
            On success: a labeled block containing the document's filename
            and its full extracted text. On unsupported `document_type` or
            when no document of that type is available for the candidate,
            a single-line error string per FR-2.
        """
        start = time.perf_counter()
        status = "ok"
        try:
            if document_type not in _FULL_DOC_TYPES:
                status = "invalid_type"
                return (
                    f"Unsupported document_type '{document_type}'. "
                    "Valid: cv, life_story, recommendation_letter, grade_sheet."
                )

            repo = UploadedFileRepository(session)
            doc = await repo.get_latest_full_text_by_document_type(
                candidate_id, document_type
            )
            if doc is None:
                status = "missing"
                return (
                    f"No document of type '{document_type}' "
                    "uploaded for this candidate."
                )

            return (
                f"[{doc.document_type} — full text: {doc.filename}]\n"
                f"{doc.text}\n"
                f"[End {doc.document_type}]"
            )
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "agent_tool name=get_full_document document_type=%s status=%s duration_ms=%s",
                document_type,
                status,
                elapsed_ms,
            )

    async def save_artifact(
        artifact_type: str,
        title: str,
        body: str,
        school_name: str | None,
    ) -> str:
        """
        Persist a generated artifact (a CV draft or an essay draft) so the
        candidate can download it from the UI.

        Call this once you have produced a concrete deliverable — e.g. after
        rewriting the candidate's CV or drafting an essay. Do not call it for
        advice, outlines, or clarifying messages; only for final artifacts
        the candidate should be able to download.

        Args:
            artifact_type: Either "cv_draft" or "essay_draft".
            title: Short human-readable title for the artifact.
            body: The full text of the artifact (markdown is fine).
            school_name: The target school if the artifact is school-specific,
                otherwise None.

        Returns:
            A JSON string with `artifact_id`, `artifact_type`, `title`,
            `school_name`, and `download_url`.
        """
        start = time.perf_counter()
        try:
            if artifact_type not in {"cv_draft", "essay_draft"}:
                return json.dumps({"error": "invalid artifact_type"})

            if artifact_type == "cv_draft":
                repo = CVDraftRepository(session)
                record = await repo.create(
                    candidate_id,
                    school_name=school_name,
                    title=title,
                    body=body,
                )
            else:
                repo = EssayDraftRepository(session)
                record = await repo.create(
                    candidate_id,
                    school_name=school_name,
                    title=title,
                    body=body,
                    source="agent",
                )

            return json.dumps(
                {
                    "artifact_id": str(record.id),
                    "artifact_type": artifact_type,
                    "title": title,
                    "school_name": school_name or "",
                    # Use the Next.js same-origin API proxy so candidates can copy/paste
                    # this URL directly in the browser without hitting the frontend router.
                    "download_url": f"/api/artifacts/{record.id}/download",
                }
            )
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "agent_tool name=save_artifact artifact_type=%s school_name=%s duration_ms=%s",
                artifact_type,
                school_name or "",
                elapsed_ms,
            )

    async def _load_candidate_profile_attributes() -> dict[str, Any]:
        """Return `CandidateProfile.attributes` dict, or {} if no profile row."""
        try:
            res = await session.execute(
                select(CandidateProfile).where(
                    CandidateProfile.candidate_id == candidate_id
                )
            )
            row = res.scalar_one_or_none()
            if row is None:
                return {}
            attrs = row.attributes
            return attrs if isinstance(attrs, dict) else {}
        except Exception:
            logger.exception(
                "agent_tool rewrite_cv profile_load_failed candidate_id=%s",
                candidate_id,
            )
            return {}

    async def _load_school_dossier_text(target_school: str) -> str:
        """
        Narrow lookup of a program dossier for `target_school`. Returns the
        concatenated text of the first chunk group whose `school` matches
        (case-insensitive exact) the target school, or empty string. This is
        intentionally minimal — general wiring of `knowledge_chunks` into the
        advisor is out of scope for this feature (per spec "Out of scope").
        """
        target = (target_school or "").strip()
        if not target:
            return ""
        try:
            stmt = (
                select(KnowledgeChunk)
                .where(func.lower(KnowledgeChunk.school) == target.lower())
                .order_by(KnowledgeChunk.created_at.desc(), KnowledgeChunk.chunk_index.asc())
                .limit(40)
            )
            res = await session.execute(stmt)
            rows = list(res.scalars().all())
            if not rows:
                return ""
            # Group by source_key and pick the newest one to avoid concatenating
            # dossiers from multiple ingests of the same school.
            rows_by_source: dict[str, list[KnowledgeChunk]] = {}
            for r in rows:
                rows_by_source.setdefault(r.source_key, []).append(r)
            newest_source = max(
                rows_by_source.items(),
                key=lambda kv: max(c.created_at for c in kv[1]),
            )[0]
            chunks = sorted(
                rows_by_source[newest_source], key=lambda c: c.chunk_index
            )
            return "\n\n".join(c.text for c in chunks if c.text)
        except Exception:
            logger.exception(
                "agent_tool rewrite_cv dossier_load_failed target_school=%s",
                target_school,
            )
            return ""

    async def rewrite_cv(target_school: str = "", emphasis: str = "") -> str:
        """
        Rewrite the candidate's latest CV, optionally tailored to a target
        school and/or a thematic emphasis. The full rewrite is persisted as
        a `cv_draft` via `save_artifact` and the rewritten body is returned
        to the advisor.

        Args:
            target_school: Optional target school name. When set, the rewriter
                will be given that school's dossier (if a matching one exists
                in `knowledge_chunks`); unmatched schools are silently ignored.
            emphasis: Optional short hint about what to emphasize in the
                rewrite (e.g. "global leadership", "quantitative impact").

        Returns:
            The rewritten CV body as a string on success. If no CV with
            extracted text is available for this candidate, returns the
            explicit error string from FR-3 without persisting anything.
        """
        start = time.perf_counter()
        status = "ok"
        try:
            repo = UploadedFileRepository(session)
            cv_doc = await repo.get_latest_full_text_by_document_type(
                candidate_id, "cv"
            )
            if cv_doc is None:
                status = "missing_cv"
                return (
                    "Cannot rewrite CV: no CV document with extracted text "
                    "is available for this candidate."
                )

            life_doc = await repo.get_latest_full_text_by_document_type(
                candidate_id, "life_story"
            )
            life_text = life_doc.text if life_doc is not None else ""

            profile_attrs = await _load_candidate_profile_attributes()
            profile_json = json.dumps(profile_attrs, ensure_ascii=False)

            dossier_text = await _load_school_dossier_text(target_school)

            # Local import keeps DSPy module construction out of module-import
            # time (mirrors the pattern used elsewhere in this file).
            import os

            from app.dspy.rewrite_cv import (
                MockRewriteCVModule,
                OpenAIRewriteCVModule,
            )

            dspy_mode = (os.getenv("DSPY_MODE") or "").lower()
            module = (
                MockRewriteCVModule()
                if dspy_mode == "mock"
                else OpenAIRewriteCVModule()
            )
            pred = await module.aforward(
                cv_text=cv_doc.text,
                life_story=life_text,
                profile_json=profile_json,
                school_dossier=dossier_text,
                target_school=target_school or "",
                emphasis=emphasis or "",
            )
            rewritten = str(getattr(pred, "rewritten_cv", "") or "").strip()
            if not rewritten:
                status = "empty_rewrite"
                return (
                    "Cannot rewrite CV: the rewrite module returned no content."
                )

            title_bits = ["CV draft"]
            if target_school:
                title_bits.append(f"for {target_school}")
            title = " ".join(title_bits)
            try:
                await save_artifact(
                    "cv_draft",
                    title,
                    rewritten,
                    target_school or None,
                )
            except Exception:
                logger.exception(
                    "agent_tool rewrite_cv save_artifact_failed candidate_id=%s",
                    candidate_id,
                )
                status = "persist_failed"

            return rewritten
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "agent_tool name=rewrite_cv target_school=%s emphasis=%s status=%s duration_ms=%s",
                target_school or "",
                emphasis or "",
                status,
                elapsed_ms,
            )

    return (
        retrieve_candidate_context,
        save_artifact,
        get_full_document,
        rewrite_cv,
    )

