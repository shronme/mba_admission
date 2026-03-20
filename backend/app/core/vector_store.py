"""
pgvector helpers for document chunk storage and semantic search.

Sync functions are used by Celery workers; async functions by FastAPI routes.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def upsert_chunks_sync(
    session: Session,
    *,
    file_id: uuid.UUID,
    candidate_id: uuid.UUID,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """
    Replace all chunks for a file with a fresh set.
    Deletes existing rows first so re-processing a file is idempotent.
    """
    from app.db.models.document_chunk import DocumentChunk

    session.execute(delete(DocumentChunk).where(DocumentChunk.file_id == file_id))

    for idx, (text, embedding) in enumerate(zip(chunks, embeddings)):
        session.add(
            DocumentChunk(
                file_id=file_id,
                candidate_id=candidate_id,
                chunk_index=idx,
                text=text,
                embedding=embedding,
            )
        )

    session.flush()
    logger.info(
        "vector_store_upsert file_id=%s candidate_id=%s chunks=%s",
        file_id,
        candidate_id,
        len(chunks),
    )


async def search_async(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 6,
) -> list[str]:
    """
    Return the top-K most relevant chunk texts for a candidate, ordered by
    cosine similarity to the query embedding.
    """
    from app.db.models.document_chunk import DocumentChunk

    result = await session.execute(
        select(DocumentChunk.text)
        .where(DocumentChunk.candidate_id == candidate_id)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    chunks = list(result.scalars().all())
    logger.debug(
        "vector_store_search candidate_id=%s top_k=%s results=%s",
        candidate_id,
        top_k,
        len(chunks),
    )
    return chunks
