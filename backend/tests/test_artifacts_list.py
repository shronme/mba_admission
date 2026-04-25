from __future__ import annotations

import os
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.main import app
from app.repositories.cv_draft_repository import CVDraftRepository
from app.repositories.essay_draft_repository import EssayDraftRepository


def _make_engine_and_sessionmaker():
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    return engine, sm


async def _enter_candidate(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/candidates/enter", json={"email": email})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_list_artifacts_returns_cv_and_essay_drafts() -> None:
    os.environ["DSPY_MODE"] = "mock"
    engine, sm = _make_engine_and_sessionmaker()
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            data = await _enter_candidate(client, f"arts-{uuid.uuid4().hex[:8]}@example.com")
            candidate_id = uuid.UUID(data["candidate"]["id"])
            auth = {"Authorization": f"Bearer {data['session_token']}"}

            async with sm() as session:
                cv_repo = CVDraftRepository(session)
                essay_repo = EssayDraftRepository(session)
                await cv_repo.create(
                    candidate_id,
                    school_name="Wharton",
                    title="CV v1",
                    body="Hello",
                )
                await essay_repo.create(
                    candidate_id,
                    school_name="Wharton",
                    title="Essay v1",
                    body="Hello",
                    source="agent",
                )
                await session.commit()

            r = await client.get("/artifacts", headers=auth)
            assert r.status_code == 200, r.text
            payload = r.json()
            arts = payload.get("artifacts") or []
            assert any(a.get("artifact_type") == "cv_draft" for a in arts)
            assert any(a.get("artifact_type") == "essay_draft" for a in arts)
    finally:
        await engine.dispose()

