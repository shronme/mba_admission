from __future__ import annotations

import json
import os
import types
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.dspy.agent_tools import build_agent_tools


@pytest.mark.asyncio
async def test_save_artifact_blocks_cv_draft_without_rewrite_cv(monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ["DSPY_MODE"] = "mock"
    session = MagicMock()
    candidate_id = uuid.uuid4()
    openai_client = MagicMock()

    _retrieve, save_artifact, _get_doc, _rewrite_cv, _classify = build_agent_tools(
        session, candidate_id, openai_client
    )

    raw = await save_artifact("cv_draft", "Title", "Body", None)
    parsed = json.loads(raw)
    assert "error" in parsed
    assert "rewrite_cv" in parsed["error"]


@pytest.mark.asyncio
async def test_rewrite_cv_internal_persistence_bypasses_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ["DSPY_MODE"] = "mock"
    session = MagicMock()
    candidate_id = uuid.uuid4()
    openai_client = MagicMock()

    _retrieve, _save_artifact, _get_doc, rewrite_cv, _classify = build_agent_tools(
        session, candidate_id, openai_client
    )

    class _Doc(types.SimpleNamespace):
        pass

    async def _fake_get_latest(candidate_id_in, doc_type_in):  # noqa: ARG001
        if doc_type_in == "cv":
            return _Doc(document_type="cv", filename="cv.pdf", text="SOURCE CV")
        if doc_type_in == "life_story":
            return None
        return None

    # Avoid DB access in rewrite_cv.
    monkeypatch.setattr(
        "app.dspy.agent_tools.UploadedFileRepository.get_latest_full_text_by_document_type",
        AsyncMock(side_effect=_fake_get_latest),
        raising=True,
    )
    monkeypatch.setattr(
        "app.dspy.agent_tools.CandidateProfile",
        MagicMock(),
        raising=False,
    )

    # Make the mock rewrite module deterministic.
    class _Pred(types.SimpleNamespace):
        pass

    async def _fake_rewrite_aforward(**_kwargs):
        return _Pred(rewritten_cv="REWRITTEN CV")

    monkeypatch.setattr(
        "app.dspy.rewrite_cv.MockRewriteCVModule.aforward",
        AsyncMock(side_effect=_fake_rewrite_aforward),
        raising=True,
    )

    # Ensure the internal `save_artifact` persists without real DB.
    fake_record = types.SimpleNamespace(id=uuid.uuid4())
    create_mock = AsyncMock(return_value=fake_record)
    monkeypatch.setattr(
        "app.dspy.agent_tools.CVDraftRepository.create",
        create_mock,
        raising=True,
    )

    out = await rewrite_cv(target_school="", emphasis="", prior_feedback="")
    parsed = json.loads(out)
    assert isinstance(parsed, dict)
    assert parsed["artifact"]["artifact_type"] == "cv_draft"
    assert create_mock.await_count == 1
    _args, kwargs = create_mock.await_args
    assert kwargs["body"] == "REWRITTEN CV"

