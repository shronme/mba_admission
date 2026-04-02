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


@pytest.mark.asyncio
async def test_upload_single_file_accepts_document_type_hint(tmp_path: Path) -> None:
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
            cand = await _enter_candidate(client, "hintdoc@example.com")
            auth = {"Authorization": f"Bearer {cand['session_token']}"}

            files = [("files", ("cv.txt", b"work experience", "text/plain"))]
            data = {"document_type_hint": "cv"}
            upload_resp = await client.post("/files/upload", headers=auth, files=files, data=data)
            assert upload_resp.status_code == 200, upload_resp.text
            meta = upload_resp.json()["files"][0]
            assert meta.get("document_type") == "cv"
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_upload_rejects_document_type_hint_with_multiple_files(tmp_path: Path) -> None:
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
            cand = await _enter_candidate(client, "multihint@example.com")
            auth = {"Authorization": f"Bearer {cand['session_token']}"}
            files = [
                ("files", ("a.txt", b"a", "text/plain")),
                ("files", ("b.txt", b"b", "text/plain")),
            ]
            data = {"document_type_hint": "cv"}
            upload_resp = await client.post("/files/upload", headers=auth, files=files, data=data)
            assert upload_resp.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_patch_intake_persists_target_schools(tmp_path: Path) -> None:
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
            cand = await _enter_candidate(client, "intakeschools@example.com")
            auth = {"Authorization": f"Bearer {cand['session_token']}"}
            body = {
                "full_name": "Pat Example",
                "country_of_residence": "United States",
                "date_of_birth": "1992-06-01",
                "grad_program_focus": "mba_full_time",
                "target_schools": ["Harvard Business School", "Stanford Graduate School of Business"],
            }
            r = await client.patch("/candidates/me/intake", headers=auth, json=body)
            assert r.status_code == 200, r.text
            profile = r.json()["profile"]
            assert profile["intake_form_completed"] is True
            assert profile["attributes"]["target_schools"] == body["target_schools"]

            bad = await client.patch(
                "/candidates/me/intake",
                headers=auth,
                json={**body, "target_schools": ["Not A Real B-School"]},
            )
            assert bad.status_code == 422

            schools_resp = await client.get("/candidates/intake/target-schools", headers=auth)
            assert schools_resp.status_code == 200, schools_resp.text
            payload = schools_resp.json()
            assert "Harvard Business School" in payload["tier_1"]
            assert isinstance(payload["tier_2"], list)
            assert payload["max_selections"] == 24
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()

