"""
Tool-selection / preload-path integration tests (FR-8).

Covers TC-046 and TC-047 from the QA plan: over a seeded rewrite-class vs
Q&A-class set of messages, confirm that the deterministic FR-1 classifier
routes prompts to the full-document preload path (a proxy for
`get_full_document`) for ≥95% of the rewrite set and 0% of the Q&A set.

Also covers TC-048 as a latency proxy: on the non-matching Q&A path,
`_retrieve_doc_snippets` calls `search_async` with the existing `top_k` and
does **not** touch `UploadedFileRepository`.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DSPY_MODE", "mock")

from app.api.routes.chat import _retrieve_doc_snippets  # noqa: E402
from app.dspy.intent import classify_rewrite_intent  # noqa: E402
from app.repositories.uploaded_file_repository import FullDoc  # noqa: E402


def _fake_doc(text: str, doc_type: str) -> FullDoc:
    return FullDoc(
        filename=f"{doc_type}.pdf",
        document_type=doc_type,
        text=text,
        created_at=datetime.now(timezone.utc),
    )


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
# TC-046 — rewrite-class seeded set triggers full-doc path for ≥95%
# ===========================================================================
class TestRewriteClassRouting:
    def test_all_rewrite_seeds_classify_as_rewrite(self) -> None:
        matched = [m for m in REWRITE_SEEDS if classify_rewrite_intent(m)]
        ratio = len(matched) / len(REWRITE_SEEDS)
        assert ratio >= 0.95, (
            f"rewrite-class routing {ratio:.3f} below 0.95; "
            f"missed={[m for m in REWRITE_SEEDS if m not in matched]}"
        )


# ===========================================================================
# TC-047 — non-rewrite/Q&A seeds never force the full-doc path
# ===========================================================================
class TestQaClassRouting:
    def test_qa_seeds_do_not_classify_as_rewrite(self) -> None:
        false_positives = [m for m in QA_SEEDS if classify_rewrite_intent(m)]
        assert not false_positives, (
            f"Q&A prompts wrongly routed to full-doc path: {false_positives}"
        )


# ===========================================================================
# TC-046/TC-047 integration — preload path actually fans out correctly
# ===========================================================================
class TestPreloadFanOut:
    @pytest.mark.asyncio
    async def test_rewrite_seeds_skip_semantic_search(self) -> None:
        """
        For every rewrite-class message, `_retrieve_doc_snippets` must NOT
        call the semantic `search_async` path; it must instead pull the
        latest full CV / life-story text from `UploadedFileRepository`.
        """
        session = MagicMock()
        candidate_id = uuid.uuid4()

        with patch(
            "app.api.routes.chat.UploadedFileRepository"
        ) as repo_cls, patch(
            "app.core.vector_store.search_async", new_callable=AsyncMock
        ) as search_mock:
            repo = repo_cls.return_value

            async def _fake_latest(candidate_id, doc_type):  # type: ignore[no-untyped-def]
                return _fake_doc(f"FULL_TEXT_{doc_type.upper()}", doc_type)

            repo.get_latest_full_text_by_document_type = _fake_latest

            for msg in REWRITE_SEEDS:
                search_mock.reset_mock()
                snippets = await _retrieve_doc_snippets(
                    session=session,
                    candidate_id=candidate_id,
                    user_message=msg,
                )
                assert search_mock.call_count == 0, (
                    f"rewrite seed {msg!r} incorrectly triggered semantic search"
                )
                assert any("— full text]" in s for s in snippets), (
                    f"expected tagged full-doc block for {msg!r}, got={snippets}"
                )

    @pytest.mark.asyncio
    async def test_qa_seeds_use_semantic_search_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        TC-048 latency proxy: non-matching Q&A turns call `search_async`
        exactly once with the default top_k and never hit
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
            "app.api.routes.chat.UploadedFileRepository"
        ) as repo_cls, patch(
            "app.core.vector_store.search_async", new_callable=AsyncMock
        ) as search_mock, patch(
            "openai.AsyncOpenAI", return_value=fake_client
        ):
            search_mock.return_value = ["snippet-1", "snippet-2"]
            repo = repo_cls.return_value
            repo.get_latest_full_text_by_document_type = AsyncMock()

            for msg in QA_SEEDS:
                search_mock.reset_mock()
                repo.get_latest_full_text_by_document_type.reset_mock()
                await _retrieve_doc_snippets(
                    session=session,
                    candidate_id=candidate_id,
                    user_message=msg,
                )
                assert search_mock.call_count == 1, (
                    f"Q&A seed {msg!r} should call search_async once, "
                    f"got {search_mock.call_count}"
                )
                repo.get_latest_full_text_by_document_type.assert_not_called()


# ===========================================================================
# TC-047 — aggregate preload-path assertion over combined sets
# ===========================================================================
class TestAggregateAccuracy:
    def test_aggregate_accuracy_over_combined_set(self) -> None:
        labels: list[tuple[str, bool]] = [(m, True) for m in REWRITE_SEEDS] + [
            (m, False) for m in QA_SEEDS
        ]
        correct = 0
        mistakes: list[tuple[str, bool, bool]] = []
        for msg, expected in labels:
            predicted = classify_rewrite_intent(msg)
            if predicted == expected:
                correct += 1
            else:
                mistakes.append((msg, expected, predicted))
        accuracy = correct / len(labels)
        assert accuracy >= 0.95, (
            f"aggregate tool-selection accuracy {accuracy:.3f} < 0.95 "
            f"mistakes={mistakes}"
        )
