from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import get_db_session
from app.main import app
import app.core.storage as storage_module


@pytest.mark.asyncio
async def _enter_candidate(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/candidates/enter", json={"email": email})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_token"]
    assert data["candidate"]["id"]
    return data


@pytest.mark.asyncio
async def test_candidate_cannot_access_other_candidate_thread(
    tmp_path: Path,
) -> None:
    # Ensure local storage writes go into tmp_path (storage backend is cached).
    storage_module._BACKEND = None
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
            cand1 = await _enter_candidate(client, "cand1@example.com")
            cand2 = await _enter_candidate(client, "cand2@example.com")

            auth1 = {"Authorization": f"Bearer {cand1['session_token']}"}
            auth2 = {"Authorization": f"Bearer {cand2['session_token']}"}

            thread_resp = await client.post("/chat/threads", headers=auth1)
            assert thread_resp.status_code == 200, thread_resp.text
            thread_id = thread_resp.json()["thread_id"]

            msg_resp = await client.get(
                f"/chat/threads/{thread_id}/messages",
                headers=auth2,
            )
            assert msg_resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_chat_stream_persists_assistant_message(
    tmp_path: Path,
) -> None:
    storage_module._BACKEND = None
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
            cand = await _enter_candidate(client, "streamer@example.com")
            auth = {"Authorization": f"Bearer {cand['session_token']}"}

            thread_resp = await client.post("/chat/threads", headers=auth)
            thread_id = thread_resp.json()["thread_id"]

            async with client.stream(
                "POST",
                f"/chat/threads/{thread_id}/messages/stream",
                headers=auth,
                json={"content": "I have uploaded documents. Now what are my goals?"},
            ) as resp:
                assert resp.status_code == 200, await resp.aread()
                chunks: list[str] = []
                async for t in resp.aiter_text():
                    chunks.append(t)

            assert "".join(chunks).strip() != ""

            messages_resp = await client.get(
                f"/chat/threads/{thread_id}/messages",
                headers=auth,
            )
            assert messages_resp.status_code == 200, messages_resp.text
            messages = messages_resp.json()["messages"]
            # Last message should be the streamed assistant response.
            assert any(
                m.get("role") == "assistant" and (m.get("content") or "").strip()
                for m in messages
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_candidate_cannot_download_other_candidate_file(
    tmp_path: Path,
) -> None:
    storage_module._BACKEND = None
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
            cand1 = await _enter_candidate(client, "file1@example.com")
            cand2 = await _enter_candidate(client, "file2@example.com")

            auth1 = {"Authorization": f"Bearer {cand1['session_token']}"}
            auth2 = {"Authorization": f"Bearer {cand2['session_token']}"}

            files = [
                ("files", ("test.txt", b"hello admissions", "text/plain")),
            ]
            upload_resp = await client.post(
                "/files/upload",
                headers=auth1,
                files=files,
            )
            assert upload_resp.status_code == 200, upload_resp.text
            uploaded_files = upload_resp.json()["files"]
            assert len(uploaded_files) == 1
            file_id = uploaded_files[0]["id"]

            download_resp = await client.get(f"/files/{file_id}/download", headers=auth2)
            assert download_resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()

