"""
Tests for FR-3 `rewrite_cv` tool wrapper in `agent_tools.py`.

Covers TC-018..TC-023 from the `rag-full-document-retrieval` QA plan:
  - TC-018: happy path — returns rewrite and persists as `cv_draft`
  - TC-019: missing CV — exact error string, no `save_artifact` call
  - TC-020: missing life story — still succeeds
  - TC-021: empty profile JSON — still succeeds
  - TC-022: unknown `target_school` — dossier skipped silently
  - TC-023: back-to-back invocations persist once per call

All tests run in `DSPY_MODE=mock` so `MockRewriteCVModule` is used (no LLM
calls). `save_artifact` and `UploadedFileRepository` are patched to capture
invocations without a live DB.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["DSPY_MODE"] = "mock"

from app.dspy.agent_tools import build_agent_tools  # noqa: E402
from app.repositories.uploaded_file_repository import (  # noqa: E402
    FullDoc,
    UploadedFileRepository,
)

# ---------------------------------------------------------------------------
# Common fixtures / helpers
# ---------------------------------------------------------------------------

_CV_TEXT = (
    "JANE DOE\n"
    "Senior PM at Acme (2020 - Present)\n"
    "Data PM at Beta Inc (2017 - 2020)\n"
    "Education: Stanford University, B.S. Computer Science, 2017\n"
)

_LIFE_STORY_TEXT = "Grew up in Cairo, moved to California for college."


def _cv_doc() -> FullDoc:
    return FullDoc(
        filename="cv.pdf",
        document_type="cv",
        text=_CV_TEXT,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _life_doc() -> FullDoc:
    return FullDoc(
        filename="life.txt",
        document_type="life_story",
        text=_LIFE_STORY_TEXT,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


class _ArtifactRecorder:
    """Callable recording every `save_artifact(...)` invocation."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str | None]] = []

    async def __call__(
        self,
        artifact_type: str,
        title: str,
        body: str,
        school_name: str | None,
    ) -> str:
        self.calls.append((artifact_type, title, body, school_name))
        return json.dumps(
            {
                "artifact_id": str(uuid.uuid4()),
                "artifact_type": artifact_type,
                "title": title,
                "school_name": school_name or "",
                "download_url": "/api/artifacts/fake/download",
            }
        )


def _make_repo(cv: FullDoc | None, life: FullDoc | None) -> AsyncMock:
    repo = AsyncMock(spec=UploadedFileRepository)

    async def _get(candidate_id: uuid.UUID, doc_type: str) -> FullDoc | None:
        if doc_type == "cv":
            return cv
        if doc_type == "life_story":
            return life
        return None

    repo.get_latest_full_text_by_document_type = AsyncMock(side_effect=_get)
    return repo


async def _build_rewrite(
    *,
    cv: FullDoc | None,
    life: FullDoc | None = None,
    profile_attrs: dict[str, Any] | None = None,
    dossier_text: str = "",
):
    """Construct `build_agent_tools` output with repo/profile/dossier patched.

    Returns (rewrite_cv_callable, recorder, repo_mock).
    """
    repo = _make_repo(cv, life)
    recorder = _ArtifactRecorder()

    session = MagicMock()
    candidate_id = uuid.uuid4()
    openai_client = MagicMock()

    # Patch the three sources the tool consults:
    #   1) UploadedFileRepository (CV + life story)
    #   2) CandidateProfile via `_load_candidate_profile_attributes`
    #      (patched through `session.execute`)
    #   3) school dossier via `_load_school_dossier_text` (patched via
    #      `KnowledgeChunk` select on `session.execute`)

    # Simplify: patch _load_* helpers is not straightforward since they are
    # inner closures; instead we patch `UploadedFileRepository` and make
    # `session.execute` return profile attrs / empty dossier. But the
    # implementation does `select(CandidateProfile)` then `select(KnowledgeChunk)`,
    # so use a side_effect that inspects the compiled SQL and returns an
    # appropriate mock.

    profile_row = MagicMock()
    profile_row.attributes = profile_attrs if profile_attrs is not None else {}

    async def _execute(stmt: Any) -> MagicMock:
        sql = str(stmt).lower()
        result = MagicMock()
        if "candidate_profiles" in sql or "attributes" in sql:
            result.scalar_one_or_none = MagicMock(return_value=profile_row)
        elif "knowledge_chunks" in sql:
            # Return empty dossier by default.
            scalars = MagicMock()
            scalars.all = MagicMock(return_value=[])
            result.scalars = MagicMock(return_value=scalars)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    session.execute = AsyncMock(side_effect=_execute)

    # Build the agent tools with our patched repo and fake session.
    with patch(
        "app.dspy.agent_tools.UploadedFileRepository", return_value=repo
    ):
        retrieve_fn, save_fn, get_full_document, rewrite_cv, classify_intent = build_agent_tools(
            session, candidate_id, openai_client
        )

    # Replace save_artifact closure with our recorder at module level is
    # not possible (it's a closure). Instead, replace the `_save_artifact`
    # invocation in `rewrite_cv` by monkey-patching the tool: intercept the
    # CVDraftRepository used inside `save_artifact`.
    # Simpler path: swap the returned `save_fn` with recorder AND patch the
    # internal `save_artifact` reference via a sentinel. In the current
    # implementation, `rewrite_cv` calls `save_artifact(...)` directly from
    # the enclosing closure — we cannot intercept that at the test layer
    # without patching. So assert on the DB side instead: patch
    # `CVDraftRepository`.
    return rewrite_cv, recorder, repo, session


# ===========================================================================
# TC-018 — happy path: returns rewrite + persists cv_draft
# ===========================================================================
class TestRewriteCvHappyPath:
    @pytest.mark.asyncio
    async def test_returns_rewrite_and_persists(self) -> None:
        """Mock path preserves CV content and creates a `cv_drafts` row."""
        fake_draft = MagicMock()
        fake_draft.id = uuid.uuid4()
        cv_draft_repo = AsyncMock()
        cv_draft_repo.create = AsyncMock(return_value=fake_draft)

        repo = _make_repo(_cv_doc(), _life_doc())
        profile_row = MagicMock()
        profile_row.attributes = {"target_country": "US"}

        async def _execute(stmt: Any) -> MagicMock:
            sql = str(stmt).lower()
            result = MagicMock()
            if "candidate_profiles" in sql:
                result.scalar_one_or_none = MagicMock(return_value=profile_row)
            elif "knowledge_chunks" in sql:
                scalars = MagicMock()
                scalars.all = MagicMock(return_value=[])
                result.scalars = MagicMock(return_value=scalars)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)

        with patch(
            "app.dspy.agent_tools.UploadedFileRepository", return_value=repo
        ), patch(
            "app.dspy.agent_tools.CVDraftRepository", return_value=cv_draft_repo
        ):
            _retrieve, _save, _get_full, rewrite_cv, _classify = build_agent_tools(
                session, uuid.uuid4(), MagicMock()
            )
            result = await rewrite_cv(
                target_school="Wharton",
                emphasis="impact",
                prior_feedback="- Emphasize leadership\n- Quantify outcomes",
            )

        # Tool returns a JSON payload (artifact + change summary), not the CV body.
        assert isinstance(result, str) and result.strip()
        payload = json.loads(result)
        assert isinstance(payload, dict)
        assert isinstance(payload.get("artifact"), dict)
        assert payload["artifact"].get("artifact_id")
        assert payload["artifact"].get("download_url")
        assert "change_summary" in payload
        assert "reasoning" in payload

        # One cv_draft row persisted.
        cv_draft_repo.create.assert_awaited_once()
        kwargs = cv_draft_repo.create.call_args.kwargs
        assert kwargs.get("school_name") == "Wharton"
        assert "CV draft" in (kwargs.get("title") or "")
        assert "JANE DOE" in (kwargs.get("body") or "")


# ===========================================================================
# TC-019 — missing CV: exact error string, no save_artifact
# ===========================================================================
class TestRewriteCvMissingCv:
    @pytest.mark.asyncio
    async def test_missing_cv_returns_exact_error_and_no_persist(self) -> None:
        cv_draft_repo = AsyncMock()
        cv_draft_repo.create = AsyncMock()

        repo = _make_repo(cv=None, life=None)
        session = MagicMock()
        session.execute = AsyncMock()

        with patch(
            "app.dspy.agent_tools.UploadedFileRepository", return_value=repo
        ), patch(
            "app.dspy.agent_tools.CVDraftRepository", return_value=cv_draft_repo
        ):
            _retrieve, _save, _get_full, rewrite_cv, _classify = build_agent_tools(
                session, uuid.uuid4(), MagicMock()
            )
            result = await rewrite_cv()

        assert result == (
            "Cannot rewrite CV: no CV document with extracted text "
            "is available for this candidate."
        )
        cv_draft_repo.create.assert_not_called()


# ===========================================================================
# TC-020 — CV present, life story absent: succeeds
# ===========================================================================
class TestRewriteCvMissingLifeStory:
    @pytest.mark.asyncio
    async def test_cv_only_still_succeeds(self) -> None:
        fake_draft = MagicMock()
        fake_draft.id = uuid.uuid4()
        cv_draft_repo = AsyncMock()
        cv_draft_repo.create = AsyncMock(return_value=fake_draft)

        repo = _make_repo(cv=_cv_doc(), life=None)
        profile_row = MagicMock()
        profile_row.attributes = {}

        async def _execute(stmt: Any) -> MagicMock:
            sql = str(stmt).lower()
            result = MagicMock()
            if "candidate_profiles" in sql:
                result.scalar_one_or_none = MagicMock(return_value=profile_row)
            elif "knowledge_chunks" in sql:
                scalars = MagicMock()
                scalars.all = MagicMock(return_value=[])
                result.scalars = MagicMock(return_value=scalars)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)

        with patch(
            "app.dspy.agent_tools.UploadedFileRepository", return_value=repo
        ), patch(
            "app.dspy.agent_tools.CVDraftRepository", return_value=cv_draft_repo
        ):
            _r, _s, _g, rewrite_cv, _classify = build_agent_tools(
                session, uuid.uuid4(), MagicMock()
            )
            result = await rewrite_cv()

        payload = json.loads(result)
        assert payload.get("artifact", {}).get("artifact_id")
        cv_draft_repo.create.assert_awaited_once()


# ===========================================================================
# TC-021 — empty profile JSON
# ===========================================================================
class TestRewriteCvEmptyProfile:
    @pytest.mark.asyncio
    async def test_empty_profile_runs_without_error(self) -> None:
        fake_draft = MagicMock()
        fake_draft.id = uuid.uuid4()
        cv_draft_repo = AsyncMock()
        cv_draft_repo.create = AsyncMock(return_value=fake_draft)

        repo = _make_repo(cv=_cv_doc(), life=None)
        # Simulate no profile row
        async def _execute(stmt: Any) -> MagicMock:
            sql = str(stmt).lower()
            result = MagicMock()
            if "candidate_profiles" in sql:
                result.scalar_one_or_none = MagicMock(return_value=None)
            elif "knowledge_chunks" in sql:
                scalars = MagicMock()
                scalars.all = MagicMock(return_value=[])
                result.scalars = MagicMock(return_value=scalars)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)

        with patch(
            "app.dspy.agent_tools.UploadedFileRepository", return_value=repo
        ), patch(
            "app.dspy.agent_tools.CVDraftRepository", return_value=cv_draft_repo
        ):
            _r, _s, _g, rewrite_cv, _classify = build_agent_tools(
                session, uuid.uuid4(), MagicMock()
            )
            result = await rewrite_cv()

        payload = json.loads(result)
        assert isinstance(payload, dict)
        assert payload.get("artifact", {}).get("artifact_id")
        cv_draft_repo.create.assert_awaited_once()


# ===========================================================================
# TC-022 — unknown target_school: dossier silently skipped
# ===========================================================================
class TestRewriteCvUnknownSchool:
    @pytest.mark.asyncio
    async def test_unknown_school_silent_skip(self) -> None:
        fake_draft = MagicMock()
        fake_draft.id = uuid.uuid4()
        cv_draft_repo = AsyncMock()
        cv_draft_repo.create = AsyncMock(return_value=fake_draft)

        repo = _make_repo(cv=_cv_doc(), life=None)

        # Return empty dossier row list.
        async def _execute(stmt: Any) -> MagicMock:
            sql = str(stmt).lower()
            result = MagicMock()
            if "candidate_profiles" in sql:
                pr = MagicMock()
                pr.attributes = {}
                result.scalar_one_or_none = MagicMock(return_value=pr)
            elif "knowledge_chunks" in sql:
                scalars = MagicMock()
                scalars.all = MagicMock(return_value=[])
                result.scalars = MagicMock(return_value=scalars)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)

        with patch(
            "app.dspy.agent_tools.UploadedFileRepository", return_value=repo
        ), patch(
            "app.dspy.agent_tools.CVDraftRepository", return_value=cv_draft_repo
        ):
            _r, _s, _g, rewrite_cv, _classify = build_agent_tools(
                session, uuid.uuid4(), MagicMock()
            )
            result = await rewrite_cv(target_school="NonexistentSchoolX")

        payload = json.loads(result)
        assert payload.get("artifact", {}).get("artifact_id")
        # No errors, no exceptions; draft persisted with the given school name.
        cv_draft_repo.create.assert_awaited_once()
        kwargs = cv_draft_repo.create.call_args.kwargs
        assert kwargs.get("school_name") == "NonexistentSchoolX"


# ===========================================================================
# TC-023 — back-to-back invocations each persist a draft
# ===========================================================================
class TestRewriteCvBackToBack:
    @pytest.mark.asyncio
    async def test_two_invocations_create_two_drafts(self) -> None:
        draft_ids = [uuid.uuid4(), uuid.uuid4()]
        drafts = [MagicMock(id=draft_ids[0]), MagicMock(id=draft_ids[1])]
        cv_draft_repo = AsyncMock()
        cv_draft_repo.create = AsyncMock(side_effect=drafts)

        repo = _make_repo(cv=_cv_doc(), life=None)

        async def _execute(stmt: Any) -> MagicMock:
            sql = str(stmt).lower()
            result = MagicMock()
            if "candidate_profiles" in sql:
                pr = MagicMock()
                pr.attributes = {}
                result.scalar_one_or_none = MagicMock(return_value=pr)
            elif "knowledge_chunks" in sql:
                scalars = MagicMock()
                scalars.all = MagicMock(return_value=[])
                result.scalars = MagicMock(return_value=scalars)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)

        with patch(
            "app.dspy.agent_tools.UploadedFileRepository", return_value=repo
        ), patch(
            "app.dspy.agent_tools.CVDraftRepository", return_value=cv_draft_repo
        ):
            _r, _s, _g, rewrite_cv, _classify = build_agent_tools(
                session, uuid.uuid4(), MagicMock()
            )
            r1 = await rewrite_cv()
            r2 = await rewrite_cv(target_school="Wharton")

        p1 = json.loads(r1)
        p2 = json.loads(r2)
        assert p1.get("artifact", {}).get("artifact_id")
        assert p2.get("artifact", {}).get("artifact_id")
        assert cv_draft_repo.create.await_count == 2
