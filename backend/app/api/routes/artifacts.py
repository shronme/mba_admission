from __future__ import annotations

import io
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.api.deps.auth import get_candidate_id_from_bearer_token
from app.core.db import get_db_session
from app.repositories.cv_draft_repository import CVDraftRepository
from app.repositories.essay_draft_repository import EssayDraftRepository

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _safe_filename(value: str) -> str:
    v = (value or "").strip() or "artifact"
    v = re.sub(r"[^\w\-. ]+", "", v).strip()
    return (v[:80] or "artifact").replace(" ", "_")


@router.get("/{artifact_id}/download", response_model=None)
async def download_artifact(
    artifact_id: uuid.UUID,
    format: str | None = Query(default=None, description="docx|pdf"),
    candidate_id: uuid.UUID = Depends(get_candidate_id_from_bearer_token),
    session=Depends(get_db_session),
) -> StreamingResponse:
    if format not in {"docx", "pdf"}:
        raise HTTPException(status_code=400, detail="Invalid format") from None

    cv_repo = CVDraftRepository(session)
    essay_repo = EssayDraftRepository(session)

    record = await cv_repo.get_by_id_unscoped(artifact_id)
    if record is not None and getattr(record, "candidate_id", None) != candidate_id:
        raise HTTPException(status_code=403, detail="Forbidden") from None

    if record is None:
        record = await essay_repo.get_by_id_unscoped(artifact_id)
        if record is not None and getattr(record, "candidate_id", None) != candidate_id:
            raise HTTPException(status_code=403, detail="Forbidden") from None

    if record is None:
        raise HTTPException(status_code=404, detail="Artifact not found") from None

    title = getattr(record, "title", "") or "artifact"
    body = getattr(record, "body", "") or ""
    filename_base = _safe_filename(title)

    if format == "docx":
        from docx import Document

        doc = Document()
        doc.add_heading(title, level=1)
        for para in [p for p in body.split("\n\n") if p.strip()]:
            doc.add_paragraph(para)
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename_base}.docx"'
        }
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers,
        )

    # pdf
    from weasyprint import HTML

    html_body = "<h1>{}</h1><pre style='white-space: pre-wrap'>{}</pre>".format(
        title, body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    pdf_bytes = HTML(string=html_body).write_pdf()
    headers = {"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'}
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=headers,
    )

