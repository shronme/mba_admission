from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import uuid

from app.core.config import settings
from app.core.db import get_db_session
from app.main import app
from app.repositories.candidate_repo import CandidateRepository
import app.core.storage as storage_module


@pytest.mark.asyncio
async def test_confirm_selection_requires_evaluation_complete(tmp_path: Path) -> None:
    storage_module._BACKEND = None
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")
    os.environ["DSPY_MODE"] = "mock"

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            email = f"sel1-{uuid.uuid4().hex[:8]}@example.com"
            enter = await client.post("/candidates/enter", json={"email": email})
            assert enter.status_code == 200, enter.text
            data = enter.json()
            token = data["session_token"]
            auth = {"Authorization": f"Bearer {token}"}

            r = await client.post(
                "/candidates/me/school-selection/confirm",
                headers=auth,
                json={
                    "selected_schools": [{"school": "Harvard Business School", "program_slug": "mba"}]
                },
            )
            assert r.status_code == 409

            r2 = await client.post(
                "/candidates/me/school-selection/confirm",
                headers=auth,
                json={"selected_schools": []},
            )
            assert r2.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_advisor_thread_requires_confirmed_schools(tmp_path: Path) -> None:
    storage_module._BACKEND = None
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")
    os.environ["DSPY_MODE"] = "mock"

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            enter = await client.post("/candidates/enter", json={"email": "adv1@example.com"})
            assert enter.status_code == 200, enter.text
            data = enter.json()
            auth = {"Authorization": f"Bearer {data['session_token']}"}

            r = await client.post("/chat/advisor-threads", headers=auth)
            assert r.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_confirm_then_create_advisor_thread_then_stream(tmp_path: Path) -> None:
    storage_module._BACKEND = None
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "bucket")
    os.environ["DSPY_MODE"] = "mock"

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            enter = await client.post("/candidates/enter", json={"email": "adv2@example.com"})
            assert enter.status_code == 200, enter.text
            data = enter.json()
            token = data["session_token"]
            candidate_id = uuid.UUID(str(data["candidate"]["id"]))
            auth = {"Authorization": f"Bearer {token}"}

            # Seed an evaluation result so confirmation is allowed.
            async with sessionmaker() as session:
                repo = CandidateRepository(session)
                await repo.merge_profile_attributes(
                    candidate_id,
                    {
                        "admission_evaluation_result": {
                            "status": "complete",
                            "primary": [
                                {
                                    "school": "Harvard Business School",
                                    "program_slug": "mba",
                                    "program_display_name": "MBA",
                                    "priority_actions": ["Do X"],
                                }
                            ],
                            "extra": [],
                        }
                    },
                    overwrite=True,
                )
                await session.commit()

            confirm = await client.post(
                "/candidates/me/school-selection/confirm",
                headers=auth,
                json={
                    "selected_schools": [{"school": "Harvard Business School", "program_slug": "mba"}]
                },
            )
            assert confirm.status_code == 200, confirm.text

            th = await client.post("/chat/advisor-threads", headers=auth)
            assert th.status_code == 200, th.text
            thread_id = th.json()["thread_id"]

            async with client.stream(
                "POST",
                f"/chat/threads/{thread_id}/messages/stream",
                headers=auth,
                json={"content": "Help with my CV gaps"},
            ) as resp:
                assert resp.status_code == 200, await resp.aread()
                chunks: list[str] = []
                async for t in resp.aiter_text():
                    chunks.append(t)
            assert "".join(chunks).strip()
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()

