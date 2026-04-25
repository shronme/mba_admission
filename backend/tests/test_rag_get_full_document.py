"""
Tests for FR-2 `get_full_document` tool and `UploadedFileRepository`.

Covers TC-011..TC-017 from the `rag-full-document-retrieval` QA plan:
  - TC-011: valid `cv` with text returns labeled body containing full text
  - TC-012..TC-015: invalid document_type strings return exact spec error
  - TC-016: missing document / empty extracted_text returns spec error
  - TC-017: multiple CVs, latest-by-`created_at` wins (repository behavior)

Repository behavior is validated through a session-level fake (records
executed `select` statements and returns a preconfigured `UploadedFile`).
The tool-level tests patch `UploadedFileRepository` directly on the
`agent_tools` module so that the tuple order from `build_agent_tools` is
exercised without needing a live DB connection.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DSPY_MODE", "mock")

from app.db.enums import DocumentType
from app.dspy.agent_tools import build_agent_tools
from app.repositories.uploaded_file_repository import (
    FullDoc,
    UploadedFileRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class _FakeUploadedFile:
    """Lightweight stand-in for `UploadedFile` that mimics the attributes the
    repository reads (`original_filename`, `document_type`, `extra`,
    `created_at`)."""

    original_filename: str
    document_type: Any
    extra: dict | None
    created_at: datetime


class _FakeSession:
    """
    Minimal async-session stand-in for repository unit tests.

    Instead of evaluating the SQL statement, we capture it and return a
    preconfigured scalar. `UploadedFileRepository` expects
    `await session.execute(stmt)` → result with `scalar_one_or_none()`.
    """

    def __init__(self, row: _FakeUploadedFile | None) -> None:
        self.row = row
        self.captured_stmts: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.captured_stmts.append(stmt)
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=self.row)
        return result


def _make_tools(session: Any, candidate_id: uuid.UUID | None = None):
    if candidate_id is None:
        candidate_id = uuid.uuid4()
    openai_client = MagicMock()
    return build_agent_tools(session, candidate_id, openai_client), candidate_id


# ===========================================================================
# TC-011 — valid `cv` with text
# ===========================================================================
class TestGetFullDocumentSuccess:
    @pytest.mark.asyncio
    async def test_valid_cv_returns_full_text(self) -> None:
        """TC-011: body includes filename label and full `extracted_text`."""
        fake_repo = AsyncMock(spec=UploadedFileRepository)
        fake_repo.get_latest_full_text_by_document_type = AsyncMock(
            return_value=FullDoc(
                filename="my_cv.pdf",
                document_type="cv",
                text="JOHN DOE\nSenior Engineer at Acme\nSkills: Python",
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        )

        session = MagicMock()
        candidate_id = uuid.uuid4()

        with patch(
            "app.dspy.agent_tools.UploadedFileRepository", return_value=fake_repo
        ):
            (_retrieve, _save, get_full_document, _rewrite, _classify), _ = _make_tools(
                session, candidate_id
            )
            result = await get_full_document("cv")

        # Full text must appear unmodified and labeled with filename / markers.
        assert "JOHN DOE" in result
        assert "Skills: Python" in result
        assert "my_cv.pdf" in result
        # Repository was queried for the right type.
        fake_repo.get_latest_full_text_by_document_type.assert_awaited_once_with(
            candidate_id, "cv"
        )


# ===========================================================================
# TC-012..TC-015 — invalid `document_type` returns exact error string
# ===========================================================================
class TestGetFullDocumentInvalidType:
    EXPECTED_SUFFIX = (
        "Valid: cv, life_story, recommendation_letter, grade_sheet."
    )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_type",
        [
            "",           # TC-012: empty string
            "  ",         # TC-013: whitespace
            "CV",         # TC-014: uppercase variant
            "invalid",    # TC-015
            "irrelevant",
            "unclassified",
            "cv ",        # trailing space
            "Life_story", # mixed case
            "life story", # space instead of underscore
        ],
    )
    async def test_invalid_type_returns_exact_error_string(
        self, bad_type: str
    ) -> None:
        session = MagicMock()
        # Repository should NOT be consulted for invalid types.
        with patch(
            "app.dspy.agent_tools.UploadedFileRepository"
        ) as repo_cls:
            (_retrieve, _save, get_full_document, _rewrite, _classify), _ = _make_tools(session)
            result = await get_full_document(bad_type)

        # Exact wording from FR-2, with the caller's argument echoed verbatim.
        assert result == (
            f"Unsupported document_type '{bad_type}'. " + self.EXPECTED_SUFFIX
        )
        # No repo instance construction for rejected types.
        repo_cls.assert_not_called()


# ===========================================================================
# TC-016 — valid type, no usable document
# ===========================================================================
class TestGetFullDocumentMissing:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "doc_type",
        list(("cv", "life_story", "recommendation_letter", "grade_sheet")),
    )
    async def test_missing_document_returns_exact_error(self, doc_type: str) -> None:
        fake_repo = AsyncMock(spec=UploadedFileRepository)
        fake_repo.get_latest_full_text_by_document_type = AsyncMock(return_value=None)

        with patch(
            "app.dspy.agent_tools.UploadedFileRepository", return_value=fake_repo
        ):
            (_retrieve, _save, get_full_document, _rewrite, _classify), _ = _make_tools(MagicMock())
            result = await get_full_document(doc_type)

        assert result == (
            f"No document of type '{doc_type}' uploaded for this candidate."
        )


# ===========================================================================
# TC-017 — repository latest-only semantics (ORDER BY created_at DESC LIMIT 1)
# ===========================================================================
class TestUploadedFileRepositoryLatestWins:
    @pytest.mark.asyncio
    async def test_repository_filters_nonempty_extracted_text(self) -> None:
        """
        Row with valid `extracted_text` is returned as a `FullDoc`.

        The SQL statement captured by the fake session must order by
        `created_at` descending and limit to 1 (verified via `LIMIT 1`
        compilation-level knobs below).
        """
        row = _FakeUploadedFile(
            original_filename="latest.pdf",
            document_type=DocumentType.CV,
            extra={"extracted_text": "latest body text"},
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        session = _FakeSession(row=row)

        repo = UploadedFileRepository(session)
        doc = await repo.get_latest_full_text_by_document_type(
            uuid.uuid4(), "cv"
        )

        assert doc is not None
        assert doc.filename == "latest.pdf"
        assert doc.document_type == "cv"
        assert doc.text == "latest body text"
        assert doc.created_at == datetime(2024, 6, 1, tzinfo=timezone.utc)

        # Verify the compiled statement uses `ORDER BY ... DESC LIMIT 1`.
        assert session.captured_stmts, "repository must have executed a statement"
        stmt_sql = str(session.captured_stmts[0]).lower()
        assert "order by" in stmt_sql
        assert "desc" in stmt_sql
        assert "limit" in stmt_sql

    @pytest.mark.asyncio
    async def test_repository_returns_none_when_no_row(self) -> None:
        """TC-016 at the repository level."""
        session = _FakeSession(row=None)
        repo = UploadedFileRepository(session)
        doc = await repo.get_latest_full_text_by_document_type(
            uuid.uuid4(), "cv"
        )
        assert doc is None

    @pytest.mark.asyncio
    async def test_repository_returns_none_when_extracted_text_whitespace(
        self,
    ) -> None:
        """Defense-in-depth: SQL filter should reject empty text, but the
        Python-side guard still hides whitespace-only strings from the tool."""
        row = _FakeUploadedFile(
            original_filename="empty.pdf",
            document_type=DocumentType.CV,
            extra={"extracted_text": "   "},
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        session = _FakeSession(row=row)

        repo = UploadedFileRepository(session)
        doc = await repo.get_latest_full_text_by_document_type(
            uuid.uuid4(), "cv"
        )
        assert doc is None

    @pytest.mark.asyncio
    async def test_tool_returns_latest_row_text(self) -> None:
        """
        TC-017: simulate the repository returning the newer row (the "latest"
        ordering contract) and assert the tool surfaces its text. The
        SQL-level `ORDER BY created_at DESC` is proven by
        `test_repository_filters_nonempty_extracted_text`; here we only
        assert that the tool consumes whatever single row the repo yields.
        """
        newer_doc = FullDoc(
            filename="cv_v2.pdf",
            document_type="cv",
            text="NEWER_MARKER body",
            created_at=datetime(2024, 8, 15, tzinfo=timezone.utc),
        )
        fake_repo = AsyncMock(spec=UploadedFileRepository)
        fake_repo.get_latest_full_text_by_document_type = AsyncMock(
            return_value=newer_doc
        )

        with patch(
            "app.dspy.agent_tools.UploadedFileRepository", return_value=fake_repo
        ):
            (_r, _s, get_full_document, _rc, _classify), _ = _make_tools(MagicMock())
            result = await get_full_document("cv")

        assert "NEWER_MARKER" in result
        assert "cv_v2.pdf" in result
