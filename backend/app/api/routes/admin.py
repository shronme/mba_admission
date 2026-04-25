"""
Admin-only routes. All endpoints require a valid UserSession token with role=admin.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_admin_from_bearer_token
from app.core.db import get_db_session
from app.core.job_runner import JobType, job_runner
from app.core.storage import get_storage_backend, storage_key_for_upload
from app.db.enums import FileStatus
from app.db.models.candidate import Candidate
from app.db.models.files import UploadedFile
from app.db.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _file_to_dto(f: UploadedFile) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "original_filename": f.original_filename,
        "content_type": f.content_type,
        "byte_size": f.byte_size,
        "status": f.status.value,
        "document_type": f.document_type.value if f.document_type else None,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _candidate_list_dto(c: Candidate) -> dict[str, Any]:
    completeness = 0
    profile_complete = False
    if c.profile is not None:
        completeness = c.profile.completeness_score
        profile_complete = c.profile.profile_complete
    return {
        "id": str(c.id),
        "email": c.user.email,
        "full_name": c.user.full_name,
        "program_type": c.program_type.value,
        "status": c.status.value,
        "stage": c.stage.value,
        "completeness_score": completeness,
        "profile_complete": profile_complete,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _candidate_detail_dto(c: Candidate) -> dict[str, Any]:
    profile: dict[str, Any] | None = None
    if c.profile is not None:
        p = c.profile
        profile = {
            "headline": p.headline,
            "summary": p.summary,
            "attributes": p.attributes or {},
            "profile_complete": p.profile_complete,
            "completeness_score": p.completeness_score,
            "country_of_residence": p.country_of_residence,
            "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
            "intake_form_completed": p.intake_form_completed,
            "grad_program_focus": p.grad_program_focus,
        }
    files = [
        _file_to_dto(f)
        for f in (c.uploaded_files or [])
        if f.status != FileStatus.DELETED
    ]
    files.sort(key=lambda f: f["created_at"] or "", reverse=True)
    return {
        "id": str(c.id),
        "email": c.user.email,
        "full_name": c.user.full_name,
        "program_type": c.program_type.value,
        "status": c.status.value,
        "stage": c.stage.value,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "profile": profile,
        "files": files,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/candidates", response_model=None)
async def list_candidates(
    admin: User = Depends(get_admin_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(Candidate)
        .options(
            selectinload(Candidate.user),
            selectinload(Candidate.profile),
        )
        .order_by(Candidate.created_at.desc()),
    )
    candidates = list(result.scalars().all())
    logger.info("admin_list_candidates admin_user_id=%s count=%s", admin.id, len(candidates))
    return {"candidates": [_candidate_list_dto(c) for c in candidates]}


@router.get("/candidates/{candidate_id}", response_model=None)
async def get_candidate_detail(
    candidate_id: UUID,
    admin: User = Depends(get_admin_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(Candidate)
        .options(
            selectinload(Candidate.user),
            selectinload(Candidate.profile),
            selectinload(Candidate.uploaded_files),
        )
        .where(Candidate.id == candidate_id),
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    logger.info("admin_get_candidate admin_user_id=%s candidate_id=%s", admin.id, candidate_id)
    return _candidate_detail_dto(candidate)


@router.post("/candidates/{candidate_id}/files/upload", response_model=None)
async def upload_file_for_candidate(
    candidate_id: UUID,
    files: list[UploadFile] = File(...),
    admin: User = Depends(get_admin_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(Candidate).where(Candidate.id == candidate_id),
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    storage = get_storage_backend()
    logger.info(
        "admin_upload_files admin_user_id=%s candidate_id=%s file_count=%s",
        admin.id, candidate_id, len(files),
    )

    uploaded: list[UploadedFile] = []
    for uf in files:
        original_filename = uf.filename or "upload"
        content_type = uf.content_type

        row = UploadedFile(
            candidate_id=candidate_id,
            original_filename=original_filename,
            content_type=content_type,
            byte_size=None,
            storage_uri="pending",
            status=FileStatus.UPLOADING,
            extra=None,
        )
        session.add(row)
        await session.flush()

        try:
            data = await uf.read()
            byte_size = len(data)
            key = storage_key_for_upload(
                candidate_id=str(candidate_id),
                file_id=str(row.id),
                filename=original_filename,
            )
            storage_uri = storage.put_bytes(key=key, data=data, content_type=content_type)
            row.byte_size = byte_size
            row.storage_uri = storage_uri
        except Exception as e:  # noqa: BLE001
            row.status = FileStatus.FAILED
            row.extra = {"error": str(e)}
            logger.exception("admin_upload file_failed file_id=%s error=%s", row.id, str(e))

        uploaded.append(row)

    await session.commit()

    for f in uploaded:
        if f.status == FileStatus.UPLOADING:
            try:
                job_runner.enqueue(JobType.PROCESS_UPLOADED_DOCUMENT, {"file_id": str(f.id)})
            except Exception:
                logger.exception("admin_upload task_enqueue_failed file_id=%s", f.id)

    return {"files": [_file_to_dto(f) for f in uploaded]}


@router.post("/files/{file_id}/reprocess", response_model=None)
async def reprocess_uploaded_file(
    file_id: UUID,
    admin: User = Depends(get_admin_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Re-run document processing (text extraction + classification + embeddings)
    for an existing upload.

    This is useful when extraction logic changes and you want existing rows'
    `extra["extracted_text"]` to be refreshed without re-uploading the file.
    """
    row = await session.get(UploadedFile, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        job_runner.enqueue(JobType.PROCESS_UPLOADED_DOCUMENT, {"file_id": str(row.id)})
    except Exception:
        logger.exception("admin_reprocess task_enqueue_failed file_id=%s", row.id)
        raise HTTPException(status_code=500, detail="Failed to enqueue reprocess job") from None

    logger.info(
        "admin_reprocess_file admin_user_id=%s file_id=%s candidate_id=%s filename=%s",
        admin.id,
        row.id,
        row.candidate_id,
        row.original_filename,
    )
    return {"status": "enqueued", "file_id": str(row.id)}
