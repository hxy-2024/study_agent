import uuid
from dataclasses import dataclass, replace
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SourceChunk
from app.domain.rag.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class RetrievedChunk:
    id: uuid.UUID
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    source_id: uuid.UUID
    chunk_index: int
    text: str
    citation: dict[str, Any]
    embedding: list[float]
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    score: float


def dot_product(left: Sequence[float], right: Sequence[float]) -> float:
    _validate_vector(left, "left")
    _validate_vector(right, "right")
    if len(left) != len(right):
        raise ValueError("Vectors must have the same dimension")
    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))


def _validate_vector(vector: Sequence[float], name: str) -> None:
    if len(vector) == 0:
        raise ValueError(f"{name} vector must not be empty")


def _validate_limit(limit: int) -> None:
    if limit < 1:
        raise ValueError("limit must be at least 1")


def rank_chunks_by_dot_product(
    query_embedding: Sequence[float],
    chunks: Sequence[RetrievedChunk],
    limit: int,
) -> list[RetrievedChunk]:
    _validate_limit(limit)
    _validate_vector(query_embedding, "query_embedding")
    scored_chunks = [
        replace(chunk, score=dot_product(query_embedding, chunk.embedding))
        for chunk in chunks
    ]
    return sorted(
        scored_chunks,
        key=lambda chunk: (-chunk.score, chunk.source_id.int, chunk.chunk_index, chunk.id.int),
    )[:limit]


async def retrieve_chunks(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    query: str,
    limit: int,
    embedding_provider: EmbeddingProvider,
) -> list[RetrievedChunk]:
    _validate_limit(limit)
    query_embedding = embedding_provider.embed_text(query)
    result = await session.execute(
        select(SourceChunk).where(
            SourceChunk.tenant_id == tenant_id,
            SourceChunk.study_space_id == study_space_id,
            SourceChunk.is_active.is_(True),
            SourceChunk.embedding_provider == embedding_provider.provider_key,
            SourceChunk.embedding_model == embedding_provider.model_name,
            SourceChunk.embedding_dimension == len(query_embedding),
        ).order_by(SourceChunk.source_id, SourceChunk.chunk_index, SourceChunk.id)
    )
    chunks = [
        RetrievedChunk(
            id=row.id,
            tenant_id=row.tenant_id,
            study_space_id=row.study_space_id,
            source_id=row.source_id,
            chunk_index=row.chunk_index,
            text=row.text,
            citation=row.citation,
            embedding=list(row.embedding),
            embedding_provider=row.embedding_provider,
            embedding_model=row.embedding_model,
            embedding_dimension=row.embedding_dimension,
            score=0.0,
        )
        for row in result.scalars().all()
    ]
    return rank_chunks_by_dot_product(query_embedding=query_embedding, chunks=chunks, limit=limit)
