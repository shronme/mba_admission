from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Enum as SQLEnum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import FileStatus
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UploadedFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Metadata for a user upload. **File bytes are not stored in Postgres.**

    Point `storage_uri` at object storage (e.g. Railway **Storage Buckets**, S3, R2):
    `s3://bucket/key`, `https://…`, or another stable locator your app understands.
    Serve private objects via **presigned URLs** from the API (or a small proxy).
    """

    __tablename__ = "uploaded_files"
    __table_args__ = (
        Index("ix_uploaded_files_candidate_id", "candidate_id"),
        Index("ix_uploaded_files_status", "status"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[FileStatus] = mapped_column(
        SQLEnum(FileStatus, name="file_status", native_enum=True),
        nullable=False,
        default=FileStatus.READY,
        insert_default=FileStatus.READY,
    )
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="uploaded_files")
