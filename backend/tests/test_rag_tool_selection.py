"""
Tool-selection / preload-path integration tests (FR-8).

After removing the regex-gated full-document preload, `_retrieve_doc_snippets`
must always use semantic retrieval (when OPENAI_API_KEY is set) and must never
hit `UploadedFileRepository.get_latest_full_text_by_document_type` based on
message phrasing.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DSPY_MODE", "mock")

from app.api.routes.chat import _retrieve_doc_snippets  # noqa: E402


# ---------------------------------------------------------------------------
# Seeded message sets
# ---------------------------------------------------------------------------
REWRITE_SEEDS = [
    "Can you rewrite my CV for Stanford?",
    "Please polish my resume for Wharton applications",
    "I'd like to revise my essay before submitting",
    "Could you redraft my statement of purpose this week",
    "Help me edit my SOP for Booth",
    "Improve my résumé please, focus on impact",
    "Redo my life story to sound more authentic",
    "Rework the resume to emphasize leadership",
    "I want to rewrite the essay about my career change",
    "Polish my CV so recruiters notice it",
    "Can you revise the statement of purpose I uploaded",
    "Redraft my SOP with a stronger opening paragraph",
    "My CV needs a rewrite — can you help?",
    "Please edit my life story with better flow",
    "Rework my essay for Columbia",
    "Redo the CV please, the bullets feel weak",
    "Can you improve my SOP?",
    "Rewrite my resume for finance roles",
    "I want to polish the essay draft I shared",
    "Revise my CV to highlight quantified outcomes",
]

QA_SEEDS = [
    "Summarize my leadership experience",
    "What's my GMAT percentile again?",
    "Tell me about my candidacy strengths",
    "How does my profile compare to Wharton's class?",
    "List the internships from my CV",
    "What did I study in undergrad?",
    "Which schools should I consider?",
    "Have I volunteered internationally?",
    "What are my quantitative credentials?",
    "Give me a timeline of my career",
    "Do I have any publications listed?",
    "What makes me competitive for Harvard?",
    "When did I start my current role?",
    "Show me my strongest differentiators",
    "Explain my post-MBA goals as written",
    "Which recommenders should I pick?",
    "Have I mentioned any awards in my life story?",
    "What weaknesses might adcom see?",
    "Is my GMAT enough for top 10?",
    "How do I compare to the median applicant?",
]


# ===========================================================================
# Semantic-only preload path
# ===========================================================================
class TestPreloadFanOut:
    @pytest.mark.asyncio
    async def test_rewrite_like_seeds_use_semantic_search_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        For rewrite-like phrasing, `_retrieve_doc_snippets` must still use the
        semantic `search_async` path (when OPENAI_API_KEY is set) and must NOT
        consult `UploadedFileRepository.get_latest_full_text_by_document_type`.
        """
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-tests")
        session = MagicMock()
        candidate_id = uuid.uuid4()

        fake_client = MagicMock()
        fake_client.embeddings.create = AsyncMock(
            return_value=MagicMock(data=[MagicMock(embedding=[0.0] * 8)])
        )

        with patch(
            "app.repositories.uploaded_file_repository.UploadedFileRepository.get_latest_full_text_by_document_type",
            new_callable=AsyncMock,
        ) as get_latest_full_text, patch(
            "app.core.vector_store.search_async", new_callable=AsyncMock
        ) as search_mock, patch(
            "openai.AsyncOpenAI", return_value=fake_client
        ):
            search_mock.return_value = ["snippet-1", "snippet-2"]

            for msg in REWRITE_SEEDS:
                search_mock.reset_mock()
                snippets = await _retrieve_doc_snippets(
                    session=session,
                    candidate_id=candidate_id,
                    user_message=msg,
                )
                assert search_mock.call_count == 1, (
                    f"rewrite seed {msg!r} should call search_async once, "
                    f"got {search_mock.call_count}"
                )
                get_latest_full_text.assert_not_called()
                assert snippets == ["snippet-1", "snippet-2"]

    @pytest.mark.asyncio
    async def test_qa_seeds_use_semantic_search_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Q&A turns call `search_async` exactly once and never hit
        `UploadedFileRepository.get_latest_full_text_by_document_type`.
        """
        # Ensure the semantic branch is taken (requires OPENAI_API_KEY).
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-tests")

        session = MagicMock()
        candidate_id = uuid.uuid4()

        fake_client = MagicMock()
        fake_client.embeddings.create = AsyncMock(
            return_value=MagicMock(data=[MagicMock(embedding=[0.0] * 8)])
        )

        with patch(
            "app.repositories.uploaded_file_repository.UploadedFileRepository.get_latest_full_text_by_document_type",
            new_callable=AsyncMock,
        ) as get_latest_full_text, patch(
            "app.core.vector_store.search_async", new_callable=AsyncMock
        ) as search_mock, patch(
            "openai.AsyncOpenAI", return_value=fake_client
        ):
            search_mock.return_value = ["snippet-1", "snippet-2"]

            for msg in QA_SEEDS:
                search_mock.reset_mock()
                get_latest_full_text.reset_mock()
                await _retrieve_doc_snippets(
                    session=session,
                    candidate_id=candidate_id,
                    user_message=msg,
                )
                assert search_mock.call_count == 1, (
                    f"Q&A seed {msg!r} should call search_async once, "
                    f"got {search_mock.call_count}"
                )
                get_latest_full_text.assert_not_called()
