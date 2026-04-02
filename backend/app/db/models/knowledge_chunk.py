from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

_EMBED_DIM = 1536


class KnowledgeChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Vector chunks for reference knowledge (e.g. program dossier JSON ingested from S3).
    Not tied to candidate uploads or `uploaded_files`.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("source_key", "chunk_index", name="uq_knowledge_chunks_source_chunk_idx"),
        Index("ix_knowledge_chunks_source_key", "source_key"),
        Index("ix_knowledge_chunks_school_program_slug", "school", "program_slug"),
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    source_key: Mapped[str] = mapped_column(String(512), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(_EMBED_DIM), nullable=False)

    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    school: Mapped[str | None] = mapped_column(String(512), nullable=True)
    program_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    section: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chunk_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
