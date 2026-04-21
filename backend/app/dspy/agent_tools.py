from __future__ import annotations

import json
import logging
import time
import uuid
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.vector_store import search_async
from app.repositories.cv_draft_repository import CVDraftRepository
from app.repositories.essay_draft_repository import EssayDraftRepository

logger = logging.getLogger(__name__)


def build_agent_tools(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    openai_client: Any,
) -> tuple[
    Callable[[str], Awaitable[str]],
    Callable[[str, str, str, str | None], Awaitable[str]],
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

    return retrieve_candidate_context, save_artifact

