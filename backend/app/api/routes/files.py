from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote

from app.api.deps.auth import get_candidate_id_from_bearer_token
from app.core.db import get_db_session
from app.core.storage import get_storage_backend, storage_key_for_upload
from app.db.enums import FileStatus
from app.db.models.files import UploadedFile

router = APIRouter(prefix="/files", tags=["files"])

logger = logging.getLogger(__name__)


def _file_to_dto(f: UploadedFile) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "original_filename": f.original_filename,
        "content_type": f.content_type,
        "byte_size": f.byte_size,
        "status": f.status.value,
        "document_type": f.document_type.value if f.document_type else None,
    }


@router.get("", response_model=None)
async def list_files(
    candidate_id: UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(UploadedFile)
        .where(UploadedFile.candidate_id == candidate_id)
        .where(UploadedFile.status != FileStatus.DELETED)
        .order_by(UploadedFile.created_at.desc()),
    )
    files = list(result.scalars().all())
    logger.info("files_list candidate_id=%s count=%s", candidate_id, len(files))
    return {"files": [_file_to_dto(f) for f in files]}


@router.post("/upload", response_model=None)
async def upload_files(
    files: list[UploadFile] = File(...),
    candidate_id: UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    storage = get_storage_backend()
    logger.info("files_upload start candidate_id=%s file_count=%s", candidate_id, len(files))

    uploaded: list[UploadedFile] = []
    for uf in files:
        original_filename = uf.filename or "upload"
        content_type = uf.content_type

        # Create metadata row first (so we get a stable file id for the object key).
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
            logger.info(
                "files_upload file_created file_id=%s original_filename=%s content_type=%s byte_size=%s",
                row.id,
                original_filename,
                content_type,
                byte_size,
            )

            key = storage_key_for_upload(
                candidate_id=str(candidate_id),
                file_id=str(row.id),
                filename=original_filename,
            )
            storage_uri = storage.put_bytes(
                key=key,
                data=data,
                content_type=content_type,
            )

            row.byte_size = byte_size
            row.storage_uri = storage_uri
            # Status stays UPLOADING until the background task completes.
        except Exception as e:  # noqa: BLE001
            row.status = FileStatus.FAILED
            row.extra = {"error": str(e)}
            logger.exception(
                "files_upload file_failed file_id=%s original_filename=%s error=%s",
                row.id,
                original_filename,
                str(e),
            )

        uploaded.append(row)

    await session.commit()

    # Enqueue background processing for every successfully stored file.
    from app.workers.tasks.document_processing import process_uploaded_document

    for f in uploaded:
        if f.status == FileStatus.UPLOADING:
            try:
                process_uploaded_document.delay(str(f.id))
                logger.info("files_upload task_enqueued file_id=%s", f.id)
            except Exception:
                logger.exception(
                    "files_upload task_enqueue_failed file_id=%s — processing will not run",
                    f.id,
                )

    logger.info("files_upload done candidate_id=%s count=%s", candidate_id, len(uploaded))
    return {"files": [_file_to_dto(f) for f in uploaded]}


@router.get("/{file_id}/download", response_model=None)
async def download_file(
    file_id: UUID,
    candidate_id: UUID = Depends(get_candidate_id_from_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    logger.info("files_download start candidate_id=%s file_id=%s", candidate_id, file_id)
    row = await session.get(UploadedFile, file_id)
    if row is None or row.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="File not found")

    if row.storage_uri == "pending" or row.status != FileStatus.READY:
        logger.warning(
            "files_download not_ready file_id=%s status=%s storage_uri=%s",
            file_id,
            getattr(row.status, "value", row.status),
            row.storage_uri,
        )
        raise HTTPException(status_code=409, detail="File not ready")

    storage = get_storage_backend()
    stream, inferred_content_type = storage.open_stream(storage_uri=row.storage_uri)

    media_type = inferred_content_type or row.content_type or "application/octet-stream"

    # Starlette encodes response headers as latin-1. If the original filename
    # contains non-latin1 characters, this can crash the response generation.
    # Use an ASCII fallback + RFC 5987 `filename*` for UTF-8.
    raw_filename = row.original_filename or "download"
    ascii_fallback = raw_filename.encode("latin-1", "ignore").decode("latin-1") or "download"
    filename_star = quote(raw_filename, safe="")
    content_disposition = (
        f'attachment; filename="{ascii_fallback}"; filename*=utf-8\'\'{filename_star}'
    )

    headers = {"Content-Disposition": content_disposition}
    logger.info(
        "files_download streaming file_id=%s content_type=%s byte_size=%s",
        file_id,
        media_type,
        getattr(row, "byte_size", None),
    )
    return StreamingResponse(stream, media_type=media_type, headers=headers)

