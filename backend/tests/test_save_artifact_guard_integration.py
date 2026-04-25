from __future__ import annotations

import json
import os
import types
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models.cv_draft import CVDraft
from app.dspy.agent_tools import build_agent_tools
from app.db.enums import UserRole
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.user_repo import UserRepository


def _make_engine_and_sessionmaker():
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    return engine, sm


@pytest.mark.asyncio
async def test_cv_draft_save_is_rejected_without_rewrite_cv_and_does_not_persist() -> None:
    os.environ["DSPY_MODE"] = "mock"
    engine, sm = _make_engine_and_sessionmaker()
    try:
        async with sm() as session:
            user_repo = UserRepository(session)
            user = await user_repo.create_user(
                email=f"guard-{uuid.uuid4().hex[:8]}@example.com",
                full_name="Guard Reject",
                role=UserRole.CANDIDATE,
            )
            cand_repo = CandidateRepository(session)
            candidate = await cand_repo.create_candidate(user_id=user.id)
            candidate_id = candidate.id

            _retrieve, save_artifact, _get_doc, _rewrite_cv, _classify = build_agent_tools(
                session, candidate_id, MagicMock()
            )
            raw = await save_artifact("cv_draft", "Title", "Body", None)
            parsed = json.loads(raw)
            assert "error" in parsed

            count = (
                await session.execute(
                    select(func.count(CVDraft.id)).where(CVDraft.candidate_id == candidate_id)
                )
            ).scalar_one()
            assert int(count) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rewrite_cv_internal_save_persists_cv_draft_row(monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ["DSPY_MODE"] = "mock"
    engine, sm = _make_engine_and_sessionmaker()
    try:
        async with sm() as session:
            # Create user + candidate directly (avoids ASGI/DB loop mismatch in test runs).
            user_repo = UserRepository(session)
            user = await user_repo.create_user(
                email=f"guard-ok-{uuid.uuid4().hex[:8]}@example.com",
                full_name="Guard Ok",
                role=UserRole.CANDIDATE,
            )
            cand_repo = CandidateRepository(session)
            candidate = await cand_repo.create_candidate(user_id=user.id)
            candidate_id = candidate.id

            _retrieve, _save_artifact, _get_doc, rewrite_cv, _classify = build_agent_tools(
                session, candidate_id, MagicMock()
            )

            class _Doc(types.SimpleNamespace):
                pass

            async def _fake_get_latest(candidate_id_in, doc_type_in):  # noqa: ARG001
                if doc_type_in == "cv":
                    return _Doc(document_type="cv", filename="cv.pdf", text="SOURCE CV")
                if doc_type_in == "life_story":
                    return None
                return None

            monkeypatch.setattr(
                "app.dspy.agent_tools.UploadedFileRepository.get_latest_full_text_by_document_type",
                AsyncMock(side_effect=_fake_get_latest),
                raising=True,
            )

            class _Pred(types.SimpleNamespace):
                pass

            async def _fake_rewrite_aforward(**_kwargs):
                return _Pred(rewritten_cv="REWRITTEN CV")

            monkeypatch.setattr(
                "app.dspy.rewrite_cv.MockRewriteCVModule.aforward",
                AsyncMock(side_effect=_fake_rewrite_aforward),
                raising=True,
            )

            out = await rewrite_cv(target_school="", emphasis="", prior_feedback="")
            payload = json.loads(out)
            assert payload["artifact"]["artifact_type"] == "cv_draft"

            await session.commit()

            count = (
                await session.execute(
                    select(func.count(CVDraft.id)).where(CVDraft.candidate_id == candidate_id)
                )
            ).scalar_one()
            assert int(count) == 1

            cv_draft = (
                await session.execute(
                    select(CVDraft).where(CVDraft.candidate_id == candidate_id)
                )
            ).scalars().first()
            assert cv_draft is not None
            assert cv_draft.body == "REWRITTEN CV"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_guard_recovery_sequence_fits_within_react_iteration_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Covers the intent of TC-018: if a cv_draft save is rejected by the guard,
    the trajectory can still recover by running rewrite_cv and retrying.

    This test exercises the same tool closures used by ReAct and asserts the
    configured iteration budget (max_iters=8) comfortably covers the recovery
    sequence (3 tool calls: save_artifact → rewrite_cv → save_artifact).
    """
    os.environ["DSPY_MODE"] = "mock"
    engine, sm = _make_engine_and_sessionmaker()
    try:
        async with sm() as session:
            user_repo = UserRepository(session)
            user = await user_repo.create_user(
                email=f"guard-recover-{uuid.uuid4().hex[:8]}@example.com",
                full_name="Guard Recover",
                role=UserRole.CANDIDATE,
            )
            cand_repo = CandidateRepository(session)
            candidate = await cand_repo.create_candidate(user_id=user.id)
            candidate_id = candidate.id

            # Assert the configured ReAct budget matches the spec.
            from app.dspy.agent_advisor import AgentAdvisorModule

            module = AgentAdvisorModule(
                retrieve_fn=AsyncMock(return_value=""),
                save_artifact_fn=AsyncMock(return_value="{}"),
                get_full_document_fn=AsyncMock(return_value=""),
                rewrite_cv_fn=AsyncMock(return_value=""),
                classify_intent_fn=AsyncMock(return_value="{}"),
            )
            assert getattr(module.react, "max_iters", None) == 8

            _retrieve, save_artifact, _get_doc, rewrite_cv, _classify = build_agent_tools(
                session, candidate_id, MagicMock()
            )

            # 1) Guard rejects naked cv_draft save.
            raw = await save_artifact("cv_draft", "Title", "Body", None)
            parsed = json.loads(raw)
            assert "error" in parsed

            class _Doc(types.SimpleNamespace):
                pass

            async def _fake_get_latest(candidate_id_in, doc_type_in):  # noqa: ARG001
                if doc_type_in == "cv":
                    return _Doc(document_type="cv", filename="cv.pdf", text="SOURCE CV")
                if doc_type_in == "life_story":
                    return None
                return None

            monkeypatch.setattr(
                "app.dspy.agent_tools.UploadedFileRepository.get_latest_full_text_by_document_type",
                AsyncMock(side_effect=_fake_get_latest),
                raising=True,
            )

            class _Pred(types.SimpleNamespace):
                pass

            async def _fake_rewrite_aforward(**_kwargs):
                return _Pred(rewritten_cv="REWRITTEN CV")

            monkeypatch.setattr(
                "app.dspy.rewrite_cv.MockRewriteCVModule.aforward",
                AsyncMock(side_effect=_fake_rewrite_aforward),
                raising=True,
            )

            # 2) Run rewrite_cv (sets rewrite_cv_ran and internally persists).
            rewritten_payload = json.loads(
                await rewrite_cv(target_school="", emphasis="", prior_feedback="")
            )
            assert rewritten_payload["artifact"]["artifact_type"] == "cv_draft"

            # 3) Retry save_artifact now succeeds (guard allows since rewrite_cv ran).
            raw_ok = await save_artifact("cv_draft", "Title 2", "Body 2", None)
            parsed_ok = json.loads(raw_ok)
            assert "artifact_id" in parsed_ok

            await session.commit()
    finally:
        await engine.dispose()

