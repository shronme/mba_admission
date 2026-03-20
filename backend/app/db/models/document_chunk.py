from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

# Dimensions for text-embedding-3-small
_EMBED_DIM = 1536


class DocumentChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A chunk of text extracted from an uploaded document, stored with its embedding
    for semantic (vector) search via pgvector.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_candidate_id", "candidate_id"),
        Index("ix_document_chunks_file_id", "file_id"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(_EMBED_DIM), nullable=False)
