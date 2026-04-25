"""
Semantic-only preload tests for `_retrieve_doc_snippets`.

After removing regex-gated full-document preload, `_retrieve_doc_snippets` must:
- Use semantic retrieval when `OPENAI_API_KEY` is set.
- Never call `UploadedFileRepository.get_latest_full_text_by_document_type` based on message phrasing.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DSPY_MODE", "mock")

from app.api.routes.chat import _retrieve_doc_snippets  # noqa: E402


@pytest.mark.asyncio
async def test_rewrite_like_message_uses_semantic_search_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        search_mock.return_value = ["snippet-1"]

        snippets = await _retrieve_doc_snippets(
            session=session,
            candidate_id=candidate_id,
            user_message="please rewrite my CV",
        )

        assert snippets == ["snippet-1"]
        assert search_mock.call_count == 1
        get_latest_full_text.assert_not_called()


@pytest.mark.asyncio
async def test_qa_message_uses_semantic_search_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        search_mock.return_value = ["snippet-a", "snippet-b"]

        snippets = await _retrieve_doc_snippets(
            session=session,
            candidate_id=candidate_id,
            user_message="What's my GMAT score?",
        )

        assert snippets == ["snippet-a", "snippet-b"]
        assert search_mock.call_count == 1
        get_latest_full_text.assert_not_called()

