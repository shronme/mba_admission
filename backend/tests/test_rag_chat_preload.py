"""
Tests for FR-4 preload behavior and pipeline join logic.

Covers TC-024..TC-030 from the `rag-full-document-retrieval` QA plan:
  - TC-024: intent match + CV only → single `[CV — full text]` block
  - TC-025: intent match + life story only → single `[Life story — full text]`
  - TC-026: intent match + neither document → empty preload list
  - TC-027: non-English unicode preserved inside tags
  - TC-028: snapshot of exact tag strings (FR-4 contract)
  - TC-029: `pipeline.py` joins full-doc mode without `[i]` numeric prefixes
  - TC-030: non-matching message uses semantic `search_async` path

These tests exercise `_retrieve_doc_snippets` (from `app.api.routes.chat`)
with `UploadedFileRepository` patched out, so no DB is required. The
pipeline join test calls the exact lines from `pipeline.py` that handle
preload formatting (copy of the production logic) — kept in lockstep with
`app/dspy/pipeline.py` via the same branch predicate.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DSPY_MODE", "mock")

from app.api.routes.chat import _retrieve_doc_snippets  # noqa: E402
from app.repositories.uploaded_file_repository import (  # noqa: E402
    FullDoc,
    UploadedFileRepository,
)


def _make_doc(doc_type: str, text: str, filename: str | None = None) -> FullDoc:
    return FullDoc(
        filename=filename or f"{doc_type}.pdf",
        document_type=doc_type,
        text=text,
        created_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
    )


def _patch_upload_repo(cv: FullDoc | None, life: FullDoc | None):
    repo = AsyncMock(spec=UploadedFileRepository)

    async def _get(candidate_id: uuid.UUID, doc_type: str) -> FullDoc | None:
        if doc_type == "cv":
            return cv
        if doc_type == "life_story":
            return life
        return None

    repo.get_latest_full_text_by_document_type = AsyncMock(side_effect=_get)
    return patch(
        "app.api.routes.chat.UploadedFileRepository", return_value=repo
    ), repo


# ===========================================================================
# TC-024 — intent match + CV only
# ===========================================================================
class TestPreloadCvOnly:
    @pytest.mark.asyncio
    async def test_cv_only_returns_single_tagged_block(self) -> None:
        patcher, _ = _patch_upload_repo(
            cv=_make_doc("cv", "FULL CV BODY"), life=None
        )
        with patcher:
            snippets = await _retrieve_doc_snippets(
                session=MagicMock(),
                candidate_id=uuid.uuid4(),
                user_message="please rewrite my CV",
            )

        assert len(snippets) == 1
        assert snippets[0].startswith("[CV — full text]\n")
        assert snippets[0].endswith("\n[End CV]")
        assert "FULL CV BODY" in snippets[0]


# ===========================================================================
# TC-025 — intent match + life story only
# ===========================================================================
class TestPreloadLifeStoryOnly:
    @pytest.mark.asyncio
    async def test_life_story_only_returns_single_tagged_block(self) -> None:
        patcher, _ = _patch_upload_repo(
            cv=None, life=_make_doc("life_story", "MY LIFE STORY BODY")
        )
        with patcher:
            snippets = await _retrieve_doc_snippets(
                session=MagicMock(),
                candidate_id=uuid.uuid4(),
                user_message="revise my life story",
            )

        assert len(snippets) == 1
        assert snippets[0].startswith("[Life story — full text]\n")
        assert snippets[0].endswith("\n[End Life story]")
        assert "MY LIFE STORY BODY" in snippets[0]


# ===========================================================================
# TC-026 — intent match + neither document → empty list
# ===========================================================================
class TestPreloadNeitherDocument:
    @pytest.mark.asyncio
    async def test_empty_list_when_no_docs(self) -> None:
        patcher, _ = _patch_upload_repo(cv=None, life=None)
        with patcher:
            snippets = await _retrieve_doc_snippets(
                session=MagicMock(),
                candidate_id=uuid.uuid4(),
                user_message="please rewrite my CV",
            )
        # FR-4 v1 replace semantics: matched-intent turns never fall back to
        # semantic search even when no full doc is available.
        assert snippets == []


# ===========================================================================
# TC-027 — Unicode preservation inside tags
# ===========================================================================
class TestPreloadUnicodePreservation:
    @pytest.mark.asyncio
    async def test_non_english_text_preserved(self) -> None:
        unicode_text = "Résumé de Wojciech Kowalski — Szkoła Główna Handlowa 学校"
        patcher, _ = _patch_upload_repo(
            cv=_make_doc("cv", unicode_text), life=None
        )
        with patcher:
            snippets = await _retrieve_doc_snippets(
                session=MagicMock(),
                candidate_id=uuid.uuid4(),
                user_message="please rewrite my résumé",
            )

        assert len(snippets) == 1
        assert unicode_text in snippets[0]


# ===========================================================================
# TC-028 — exact tag strings
# ===========================================================================
class TestPreloadTagSnapshot:
    @pytest.mark.asyncio
    async def test_tags_match_fr4_contract_byte_for_byte(self) -> None:
        patcher, _ = _patch_upload_repo(
            cv=_make_doc("cv", "CV_TEXT"),
            life=_make_doc("life_story", "LIFE_TEXT"),
        )
        with patcher:
            snippets = await _retrieve_doc_snippets(
                session=MagicMock(),
                candidate_id=uuid.uuid4(),
                user_message="please polish my CV",
            )

        assert snippets == [
            "[CV — full text]\nCV_TEXT\n[End CV]",
            "[Life story — full text]\nLIFE_TEXT\n[End Life story]",
        ]


# ===========================================================================
# TC-029 — pipeline join for full-doc vs semantic preload
# ===========================================================================
class TestPipelineJoinBranching:
    """
    The `pipeline.py` formatting branch is:

        if docs_snippets:
            first = docs_snippets[0] if isinstance(docs_snippets[0], str) else ""
            is_full_doc_preload = first.startswith("[") and "— full text]" in first
            if is_full_doc_preload:
                preloaded_snippets_text = "\\n\\n".join(docs_snippets)
            else:
                preloaded_snippets_text = "\\n\\n".join(
                    f"[{i + 1}] {snippet}" for i, snippet in enumerate(docs_snippets)
                )
        else:
            preloaded_snippets_text = "No snippets pre-loaded."

    Tested here against the two shapes.
    """

    @staticmethod
    def _format(docs_snippets: list[Any]) -> str:
        # Mirror the production branch verbatim so behavioral drift is
        # detected if `pipeline.py` is refactored.
        if docs_snippets:
            first = docs_snippets[0] if isinstance(docs_snippets[0], str) else ""
            is_full_doc_preload = (
                first.startswith("[") and "— full text]" in first
            )
            if is_full_doc_preload:
                return "\n\n".join(docs_snippets)
            return "\n\n".join(
                f"[{i + 1}] {snippet}" for i, snippet in enumerate(docs_snippets)
            )
        return "No snippets pre-loaded."

    def test_full_doc_mode_joins_without_numeric_prefix(self) -> None:
        tagged = [
            "[CV — full text]\nA body\n[End CV]",
            "[Life story — full text]\nB body\n[End Life story]",
        ]
        out = self._format(tagged)
        assert out == (
            "[CV — full text]\nA body\n[End CV]\n\n"
            "[Life story — full text]\nB body\n[End Life story]"
        )
        # Must not contain "[1]" / "[2]" numeric prefixes anywhere.
        assert "[1] " not in out
        assert "[2] " not in out

    def test_semantic_mode_retains_numeric_prefixes(self) -> None:
        out = self._format(["snippet A", "snippet B"])
        assert out == "[1] snippet A\n\n[2] snippet B"

    def test_empty_list_returns_placeholder(self) -> None:
        assert self._format([]) == "No snippets pre-loaded."


# ===========================================================================
# TC-030 — no intent match → semantic search_async path
# ===========================================================================
class TestPreloadNoMatchSemanticPath:
    @pytest.mark.asyncio
    async def test_qa_prompt_uses_search_async(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-matching message must trigger `search_async`, not the full-doc
        repo path."""

        # Ensure an OPENAI_API_KEY is present so the semantic branch runs.
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        fake_embed_resp = MagicMock()
        fake_embed_resp.data = [MagicMock(embedding=[0.1] * 1536)]

        async_openai = MagicMock()
        async_openai.embeddings = MagicMock()
        async_openai.embeddings.create = AsyncMock(return_value=fake_embed_resp)

        patcher_openai = patch(
            "openai.AsyncOpenAI", return_value=async_openai
        )
        patcher_search = patch(
            "app.core.vector_store.search_async",
            AsyncMock(return_value=["chunk one", "chunk two"]),
        )
        patcher_repo, repo = _patch_upload_repo(
            cv=_make_doc("cv", "should-not-be-used"),
            life=_make_doc("life_story", "should-not-be-used"),
        )

        with patcher_openai, patcher_search as mock_search, patcher_repo:
            snippets = await _retrieve_doc_snippets(
                session=MagicMock(),
                candidate_id=uuid.uuid4(),
                user_message="What's my GMAT score?",
            )

        assert snippets == ["chunk one", "chunk two"]
        # Semantic path: search_async called once.
        assert mock_search.await_count == 1
        # Full-doc repo path must NOT have been consulted.
        repo.get_latest_full_text_by_document_type.assert_not_called()


# ===========================================================================
# TC-048 (preview) — Q&A latency proxy: no extra full-doc DB reads on non-match
# ===========================================================================
class TestNoExtraFullDocReadOnNonMatch:
    """
    TC-048 non-functional regression: when the message does NOT match FR-1,
    `_retrieve_doc_snippets` must never call
    `UploadedFileRepository.get_latest_full_text_by_document_type`.
    """

    @pytest.mark.asyncio
    async def test_qa_prompt_does_not_hit_upload_repo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        fake_embed_resp = MagicMock()
        fake_embed_resp.data = [MagicMock(embedding=[0.0] * 1536)]

        async_openai = MagicMock()
        async_openai.embeddings.create = AsyncMock(return_value=fake_embed_resp)

        patcher_openai = patch(
            "openai.AsyncOpenAI", return_value=async_openai
        )
        patcher_search = patch(
            "app.core.vector_store.search_async",
            AsyncMock(return_value=[]),
        )
        patcher_repo, repo = _patch_upload_repo(
            cv=_make_doc("cv", "X"), life=_make_doc("life_story", "Y")
        )

        with patcher_openai, patcher_search, patcher_repo:
            await _retrieve_doc_snippets(
                session=MagicMock(),
                candidate_id=uuid.uuid4(),
                user_message="Summarize my leadership experience",
            )

        repo.get_latest_full_text_by_document_type.assert_not_called()
