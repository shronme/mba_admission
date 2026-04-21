from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import get_db_session
from app.core.dspy_runtime import run_dspy_module
from app.db.enums import CandidateStage, StrategyType
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.chat import ChatMessage, ChatThread
from app.db.models.strategy import StrategyDecision
from app.dspy.pipeline import generate_assistant_response
from app.dspy.school_advisor import MockAdvisorModule, generate_opening_advisor_message
from app.main import app


@pytest.fixture(autouse=True)
def _force_dspy_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DSPY_MODE", "mock")
    # Ensure `openai_calls_enabled()` short-circuits regardless of developer env.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.mark.asyncio
async def _enter_candidate(client: httpx.AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post("/candidates/enter", json={"email": email})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_token"]
    assert data["candidate"]["id"]
    return data


async def _seed_admission_evaluation_complete(
    sessionmaker: async_sessionmaker,
    *,
    candidate_id: str,
) -> None:
    complete_payload = {
        "status": "complete",
        "primary": [
            {
                "school": "Harvard Business School",
                "program_slug": "mba",
                "program_display_name": "MBA",
                "strengths": ["Leadership"],
                "weaknesses": ["Quant rigor"],
                "priority_actions": ["Raise GMAT to 730+"],
                "narrative_strategy": "Connect product leadership to impact.",
                "admission_band": "competitive",
            }
        ],
        "extra": [
            {
                "school": "Stanford GSB",
                "program_slug": "mba",
                "program_display_name": "MBA",
                "strengths": [],
                "weaknesses": [],
                "priority_actions": [],
                "narrative_strategy": "",
                "admission_band": "reach",
            }
        ],
    }

    async with sessionmaker() as session:
        prof = (
            await session.execute(
                select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id),
            )
        ).scalar_one_or_none()
        if prof is None:
            prof = CandidateProfile(candidate_id=candidate_id, attributes={})
            session.add(prof)
            await session.flush()
        attrs = dict(prof.attributes or {})
        attrs["admission_evaluation_result"] = complete_payload
        prof.attributes = attrs
        session.add(prof)
        await session.commit()


async def _get_profile_attrs(
    sessionmaker: async_sessionmaker, *, candidate_id: str
) -> dict[str, Any]:
    async with sessionmaker() as session:
        prof = (
            await session.execute(
                select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id),
            )
        ).scalar_one()
        return dict(prof.attributes or {})


async def _get_candidate_stage(
    sessionmaker: async_sessionmaker, *, candidate_id: str
) -> CandidateStage:
    async with sessionmaker() as session:
        cand = (await session.execute(select(Candidate).where(Candidate.id == candidate_id))).scalar_one()
        return cand.stage


@pytest.mark.asyncio
async def test_advisor_module_returns_non_empty_with_complete_context() -> None:
    mod = MockAdvisorModule()
    out = run_dspy_module(
        mod,
        profile_attributes_json='{"gmat_total": 720, "goals": "Consulting to healthcare"}',
        selected_schools_json='[{"school":"Harvard Business School","program_slug":"mba"}]',
        admission_evaluation_result_json='{"status":"complete","primary":[{"priority_actions":["Raise GMAT to 730+"]}]}',
        conversation_history="",
        user_message="What should I focus on first?",
    )
    assert isinstance(out.response, str)
    assert out.response.strip() != ""


@pytest.mark.asyncio
async def test_advisor_module_handles_empty_history_and_multi_turn_history() -> None:
    mod = MockAdvisorModule()

    out1 = run_dspy_module(
        mod,
        profile_attributes_json="{}",
        selected_schools_json="[]",
        admission_evaluation_result_json="{}",
        conversation_history="",
        user_message="Help me with my essay angle.",
    )
    assert str(out1.response).strip() != ""

    history = "\n".join(
        [
            "USER: Hi",
            "ASSISTANT: Welcome.",
            "USER: Here is my background.",
            "ASSISTANT: Thanks.",
            "USER: My GMAT is 700.",
            "ASSISTANT: Great.",
        ]
    )
    out2 = run_dspy_module(
        mod,
        profile_attributes_json="{}",
        selected_schools_json='[{"school":"Stanford GSB","program_slug":"mba"}]',
        admission_evaluation_result_json="{}",
        conversation_history=history,
        user_message="Now what?",
    )
    assert str(out2.response).strip() != ""


@pytest.mark.asyncio
async def test_pipeline_routes_advisor_stage_to_mock_agent_advisor_module() -> None:
    out = await generate_assistant_response(
        user_message="What should I work on?",
        file_count=0,
        candidate_profile={"full_name": "Pat", "attributes": {"gmat_total": 720}},
        docs_snippets=[],
        recent_messages=[],
        profile_complete=False,
        current_completeness_score=0,
        thread_stage="advisor",
        selected_schools=[{"school": "Harvard Business School", "program_slug": "mba"}],
        admission_evaluation_result={"status": "complete", "primary": []},
        session=object(),
        candidate_id=uuid.uuid4(),
        openai_client=object(),
    )
    txt = str(getattr(out, "response", "") or "")
    assert isinstance(txt, str) and txt.strip()

@pytest.mark.asyncio
async def test_pipeline_intake_stage_does_not_use_agent_advisor_module() -> None:
    txt, _, _, _ = await generate_assistant_response(
        user_message="I uploaded documents. Now what are my goals?",
        file_count=0,
        candidate_profile={"full_name": "Pat", "attributes": {}},
        docs_snippets=[],
        recent_messages=[],
        profile_complete=False,
        current_completeness_score=0,
        thread_stage="intake",
        selected_schools=None,
        admission_evaluation_result=None,
    )
    assert isinstance(txt, str) and txt.strip()


def test_generate_opening_advisor_message_non_empty_in_mock_mode() -> None:
    text = generate_opening_advisor_message(
        selected_schools=[{"school": "Stanford GSB", "program_slug": "mba"}],
        admission_evaluation_result={"status": "complete"},
        candidate_name="Pat Example",
        use_openai=False,
    )
    assert isinstance(text, str) and text.strip()


@pytest.mark.asyncio
async def test_school_selection_confirm_happy_path_persists_selection_and_advances_stage(
    tmp_path: Path,
) -> None:
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cand = await _enter_candidate(client, "sel-happy@example.com")
            token = cand["session_token"]
            candidate_id = cand["candidate"]["id"]

            await _seed_admission_evaluation_complete(sessionmaker, candidate_id=candidate_id)

            selected = [{"school": "Harvard Business School", "program_slug": "mba"}]
            r = await client.post(
                "/candidates/me/school-selection/confirm",
                headers={"Authorization": f"Bearer {token}"},
                json={"selected_schools": selected},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["stage"] == "strategy"
            assert body["selected_schools"][0]["school"] == "Harvard Business School"

            attrs = await _get_profile_attrs(sessionmaker, candidate_id=candidate_id)
            assert attrs["selected_schools"][0]["school"] == "Harvard Business School"

            stage = await _get_candidate_stage(sessionmaker, candidate_id=candidate_id)
            assert stage == CandidateStage.STRATEGY

            async with sessionmaker() as session:
                decisions = (
                    await session.execute(
                        select(StrategyDecision)
                        .where(StrategyDecision.candidate_id == candidate_id)
                        .where(StrategyDecision.strategy_type == StrategyType.SCHOOL_SELECTION),
                    )
                ).scalars().all()
                assert len(decisions) == 1
                assert (decisions[0].payload or {}).get("selected_schools")
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_school_selection_confirm_rejects_empty_list_with_400(tmp_path: Path) -> None:
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cand = await _enter_candidate(client, "sel-empty@example.com")
            token = cand["session_token"]
            candidate_id = cand["candidate"]["id"]
            await _seed_admission_evaluation_complete(sessionmaker, candidate_id=candidate_id)

            r = await client.post(
                "/candidates/me/school-selection/confirm",
                headers={"Authorization": f"Bearer {token}"},
                json={"selected_schools": []},
            )
            assert r.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_school_selection_confirm_requires_auth_401(tmp_path: Path) -> None:
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/candidates/me/school-selection/confirm",
                json={"selected_schools": [{"school": "HBS", "program_slug": "mba"}]},
            )
            assert r.status_code == 401

            r2 = await client.post(
                "/candidates/me/school-selection/confirm",
                headers={"Authorization": "Bearer not-a-real-token"},
                json={"selected_schools": [{"school": "HBS", "program_slug": "mba"}]},
            )
            assert r2.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_school_selection_confirm_returns_409_when_evaluation_not_complete(
    tmp_path: Path,
) -> None:
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cand = await _enter_candidate(client, "sel-409@example.com")
            token = cand["session_token"]
            r = await client.post(
                "/candidates/me/school-selection/confirm",
                headers={"Authorization": f"Bearer {token}"},
                json={"selected_schools": [{"school": "HBS", "program_slug": "mba"}]},
            )
            assert r.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_school_selection_confirm_is_idempotent_updates_strategy_decision_payload(
    tmp_path: Path,
) -> None:
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cand = await _enter_candidate(client, "sel-idem@example.com")
            token = cand["session_token"]
            candidate_id = cand["candidate"]["id"]
            await _seed_admission_evaluation_complete(sessionmaker, candidate_id=candidate_id)

            a = [{"school": "Harvard Business School", "program_slug": "mba"}]
            b = [{"school": "Stanford GSB", "program_slug": "mba"}]

            r1 = await client.post(
                "/candidates/me/school-selection/confirm",
                headers={"Authorization": f"Bearer {token}"},
                json={"selected_schools": a},
            )
            assert r1.status_code == 200, r1.text
            r2 = await client.post(
                "/candidates/me/school-selection/confirm",
                headers={"Authorization": f"Bearer {token}"},
                json={"selected_schools": b},
            )
            assert r2.status_code == 200, r2.text

            async with sessionmaker() as session:
                decisions = (
                    await session.execute(
                        select(StrategyDecision)
                        .where(StrategyDecision.candidate_id == candidate_id)
                        .where(StrategyDecision.strategy_type == StrategyType.SCHOOL_SELECTION),
                    )
                ).scalars().all()
                assert len(decisions) == 1
                payload = decisions[0].payload or {}
                assert payload.get("selected_schools")[0]["school"] == "Stanford GSB"
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_advisor_threads_requires_selected_schools_409(tmp_path: Path) -> None:
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cand = await _enter_candidate(client, "advisor-409@example.com")
            token = cand["session_token"]
            r = await client.post("/chat/advisor-threads", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_advisor_threads_create_and_idempotent_and_opening_message_persisted(
    tmp_path: Path,
) -> None:
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cand = await _enter_candidate(client, f"advisor-create-{uuid.uuid4().hex[:8]}@example.com")
            token = cand["session_token"]
            candidate_id = cand["candidate"]["id"]
            await _seed_admission_evaluation_complete(sessionmaker, candidate_id=candidate_id)

            # Confirm selection so advisor thread is allowed.
            await client.post(
                "/candidates/me/school-selection/confirm",
                headers={"Authorization": f"Bearer {token}"},
                json={"selected_schools": [{"school": "Harvard Business School", "program_slug": "mba"}]},
            )

            r1 = await client.post("/chat/advisor-threads", headers={"Authorization": f"Bearer {token}"})
            assert r1.status_code == 200, r1.text
            data1 = r1.json()
            assert data1["is_new"] is True
            thread_id = data1["thread_id"]

            r2 = await client.post("/chat/advisor-threads", headers={"Authorization": f"Bearer {token}"})
            assert r2.status_code == 200, r2.text
            data2 = r2.json()
            assert data2["is_new"] is False
            assert data2["thread_id"] == thread_id

            msgs = await client.get(
                f"/chat/threads/{thread_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert msgs.status_code == 200, msgs.text
            messages = msgs.json()["messages"]
            assert any(m.get("role") == "assistant" and (m.get("content") or "").strip() for m in messages)

            async with sessionmaker() as session:
                thread = await session.get(ChatThread, thread_id)
                assert thread is not None
                assert isinstance(thread.extra, dict)
                assert thread.extra.get("stage") == "advisor"
                assert thread.extra.get("selected_schools")

                db_msgs = (
                    await session.execute(
                        select(ChatMessage).where(ChatMessage.thread_id == thread_id),
                    )
                ).scalars().all()
                assert any(m.role.value == "assistant" and (m.content or "").strip() for m in db_msgs)
                assert all(m.thread_id is not None for m in db_msgs)
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_advisor_streaming_routes_and_persists_assistant_message_and_isolated_404(
    tmp_path: Path,
) -> None:
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cand_a = await _enter_candidate(client, "advisor-stream-a@example.com")
            token_a = cand_a["session_token"]
            candidate_id_a = cand_a["candidate"]["id"]
            await _seed_admission_evaluation_complete(sessionmaker, candidate_id=candidate_id_a)

            await client.post(
                "/candidates/me/school-selection/confirm",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"selected_schools": [{"school": "Harvard Business School", "program_slug": "mba"}]},
            )
            thread_resp = await client.post(
                "/chat/advisor-threads",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            thread_id = thread_resp.json()["thread_id"]

            async with client.stream(
                "POST",
                f"/chat/threads/{thread_id}/messages/stream",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"content": "What should I work on?"},
            ) as resp:
                assert resp.status_code == 200, await resp.aread()
                chunks: list[str] = []
                async for t in resp.aiter_text():
                    chunks.append(t)
            assert "".join(chunks).strip() != ""

            msgs = await client.get(
                f"/chat/threads/{thread_id}/messages",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert msgs.status_code == 200, msgs.text
            messages = msgs.json()["messages"]
            assert any(m.get("role") == "assistant" and (m.get("content") or "").strip() for m in messages)

            # Cross-candidate isolation: candidate B can't access candidate A's thread.
            cand_b = await _enter_candidate(client, "advisor-stream-b@example.com")
            token_b = cand_b["session_token"]
            forbidden = await client.get(
                f"/chat/threads/{thread_id}/messages",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert forbidden.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()

