from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, select

from app.db.models.files import UploadedFile
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FullDoc:
    """Lightweight view of an `UploadedFile` row used by full-document tools."""

    filename: str
    document_type: str
    text: str
    created_at: datetime


class UploadedFileRepository(BaseRepository):
    """
    Data access for `UploadedFile` rows focused on full-text retrieval for
    the RAG full-document feature. All full-document reads must go through
    this repository rather than touching the ORM from routes or DSPy tools.
    """

    async def get_latest_full_text_by_document_type(
        self,
        candidate_id: uuid.UUID,
        document_type: str,
    ) -> FullDoc | None:
        """
        Return the latest `UploadedFile` for `candidate_id` + `document_type`
        that has a non-empty `extra["extracted_text"]`, or ``None``.

        Latest-only semantics: never concatenates multiple files of the same
        type. Uses `extra->>'extracted_text' IS NOT NULL AND <> ''` to filter
        in SQL and then `ORDER BY created_at DESC LIMIT 1`.
        """
        # `UploadedFile.extra` is a JSONB column; the `->>` operator returns the
        # value at the key as text. Using SQLAlchemy's `astext` keeps the query
        # backend-agnostic (and works under sqlite in unit tests where JSONB
        # falls back to JSON with equivalent `->>` semantics).
        extracted_text_expr = UploadedFile.extra["extracted_text"].astext
        stmt = (
            select(UploadedFile)
            .where(
                and_(
                    UploadedFile.candidate_id == candidate_id,
                    UploadedFile.document_type == document_type,
                    extracted_text_expr.isnot(None),
                    extracted_text_expr != "",
                )
            )
            .order_by(UploadedFile.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            logger.info(
                "full_doc_lookup candidate_id=%s document_type=%s result=missing_row",
                str(candidate_id),
                document_type,
            )
            return None

        extra = row.extra or {}
        text = extra.get("extracted_text") if isinstance(extra, dict) else None
        if not isinstance(text, str) or not text.strip():
            # Defensive: SQL filter should already preclude this, but guard
            # against rows where JSONB contains an empty/whitespace string
            # that slipped past the `<> ''` check on some backends.
            logger.info(
                "full_doc_lookup candidate_id=%s document_type=%s result=missing_text filename=%s",
                str(candidate_id),
                document_type,
                getattr(row, "original_filename", "") or "",
            )
            return None

        doc_type_val = (
            row.document_type.value
            if hasattr(row.document_type, "value")
            else str(row.document_type)
        )
        logger.info(
            "full_doc_lookup candidate_id=%s document_type=%s result=ok filename=%s extracted_chars=%s created_at=%s",
            str(candidate_id),
            doc_type_val,
            row.original_filename,
            len(text),
            getattr(row, "created_at", None),
        )
        return FullDoc(
            filename=row.original_filename,
            document_type=doc_type_val,
            text=text,
            created_at=row.created_at,
        )
