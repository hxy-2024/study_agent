import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.rag.schemas import RetrieveRequest
from app.domain.rag.retrieval import (
    EXPECTED_EMBEDDING_DIMENSION,
    RetrievedChunk,
    dot_product,
    rank_chunks_by_dot_product,
    retrieve_chunks,
)
from app.domain.rag.embeddings import EmbeddingProvider


def _chunk(
    *,
    chunk_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    study_space_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
    chunk_index: int = 0,
    embedding: list[float] | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk_id or uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        study_space_id=study_space_id or uuid.uuid4(),
        source_id=source_id or uuid.uuid4(),
        chunk_index=chunk_index,
        text=f"chunk {chunk_index}",
        citation={"filename": f"{chunk_index}.md"},
        embedding=embedding or [1.0, 0.0],
        score=0.0,
    )


def test_rank_chunks_by_dot_product_orders_relevant_chunks() -> None:
    tenant_id = uuid.uuid4()
    space_id = uuid.uuid4()
    chunks = [
        _chunk(
            tenant_id=tenant_id,
            study_space_id=space_id,
            source_id=uuid.uuid4(),
            chunk_index=0,
            embedding=[1.0, 0.0],
        ),
        _chunk(
            tenant_id=tenant_id,
            study_space_id=space_id,
            source_id=uuid.uuid4(),
            chunk_index=1,
            embedding=[0.0, 1.0],
        ),
    ]

    ranked = rank_chunks_by_dot_product(query_embedding=[0.0, 1.0], chunks=chunks, limit=1)

    assert ranked[0].chunk_index == 1
    assert ranked[0].score == 1.0


def test_dot_product_rejects_mismatched_vector_dimensions() -> None:
    with pytest.raises(ValueError, match="same dimension"):
        dot_product([1.0, 2.0], [1.0])


def test_dot_product_rejects_empty_vectors() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        dot_product([], [])


@pytest.mark.parametrize("limit", [0, -1])
def test_rank_chunks_by_dot_product_rejects_non_positive_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be at least 1"):
        rank_chunks_by_dot_product(query_embedding=[1.0, 0.0], chunks=[_chunk()], limit=limit)


def test_rank_chunks_by_dot_product_orders_ties_deterministically() -> None:
    tenant_id = uuid.uuid4()
    space_id = uuid.uuid4()
    source_a = uuid.UUID("00000000-0000-0000-0000-000000000001")
    source_b = uuid.UUID("00000000-0000-0000-0000-000000000002")
    chunks = [
        _chunk(
            chunk_id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
            tenant_id=tenant_id,
            study_space_id=space_id,
            source_id=source_b,
            chunk_index=0,
        ),
        _chunk(
            chunk_id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
            tenant_id=tenant_id,
            study_space_id=space_id,
            source_id=source_a,
            chunk_index=1,
        ),
        _chunk(
            chunk_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            tenant_id=tenant_id,
            study_space_id=space_id,
            source_id=source_a,
            chunk_index=0,
        ),
    ]

    ranked = rank_chunks_by_dot_product(query_embedding=[1.0, 0.0], chunks=chunks, limit=3)

    assert [(chunk.source_id, chunk.chunk_index, chunk.id) for chunk in ranked] == [
        (source_a, 0, uuid.UUID("00000000-0000-0000-0000-000000000002")),
        (source_a, 1, uuid.UUID("00000000-0000-0000-0000-000000000003")),
        (source_b, 0, uuid.UUID("00000000-0000-0000-0000-000000000004")),
    ]


class _EmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = EXPECTED_EMBEDDING_DIMENSION) -> None:
        self._dimension = dimension
        self.embed_calls: list[str] = []

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return [1.0] + [0.0 for _ in range(self.dimension - 1)]


class _ScalarResult:
    def all(self) -> list[Any]:
        return []


class _ExecuteResult:
    def scalars(self) -> _ScalarResult:
        return _ScalarResult()


class _CapturingSession:
    def __init__(self) -> None:
        self.statement: Any | None = None

    async def execute(self, statement: Any) -> _ExecuteResult:
        self.statement = statement
        return _ExecuteResult()


async def test_retrieve_chunks_rejects_non_16_dimension_provider_before_embedding() -> None:
    provider = _EmbeddingProvider(dimension=2)
    session = _CapturingSession()

    with pytest.raises(ValueError, match="Embedding dimension must be 16"):
        await retrieve_chunks(
            session=session,  # type: ignore[arg-type]
            tenant_id=uuid.uuid4(),
            study_space_id=uuid.uuid4(),
            query="query",
            limit=1,
            embedding_provider=provider,
        )

    assert provider.embed_calls == []
    assert session.statement is None


async def test_retrieve_chunks_rejects_non_positive_limit_before_embedding() -> None:
    provider = _EmbeddingProvider()
    session = _CapturingSession()

    with pytest.raises(ValueError, match="limit must be at least 1"):
        await retrieve_chunks(
            session=session,  # type: ignore[arg-type]
            tenant_id=uuid.uuid4(),
            study_space_id=uuid.uuid4(),
            query="query",
            limit=0,
            embedding_provider=provider,
        )

    assert provider.embed_calls == []
    assert session.statement is None


async def test_retrieve_chunks_scopes_query_to_active_chunks_for_tenant_and_study_space() -> None:
    tenant_id = uuid.uuid4()
    space_id = uuid.uuid4()
    session = _CapturingSession()

    await retrieve_chunks(
        session=session,  # type: ignore[arg-type]
        tenant_id=tenant_id,
        study_space_id=space_id,
        query="query",
        limit=1,
        embedding_provider=_EmbeddingProvider(),
    )

    assert session.statement is not None
    statement_text = str(session.statement)
    assert "source_chunks.tenant_id = :tenant_id_1" in statement_text
    assert "source_chunks.study_space_id = :study_space_id_1" in statement_text
    assert "source_chunks.is_active IS true" in statement_text


def test_retrieve_request_does_not_accept_client_tenant_scope() -> None:
    payload = RetrieveRequest(study_space_id=uuid.uuid4(), query="matrix rank", limit=5)

    assert payload.query == "matrix rank"
    assert payload.limit == 5
    assert not hasattr(payload, "tenant_id")


def test_retrieve_request_rejects_client_tenant_scope() -> None:
    try:
        RetrieveRequest(
            tenant_id=uuid.uuid4(),
            study_space_id=uuid.uuid4(),
            query="matrix rank",
            limit=5,
        )
    except ValidationError:
        return
    raise AssertionError("Expected ValidationError")


def test_retrieve_request_rejects_empty_query() -> None:
    try:
        RetrieveRequest(study_space_id=uuid.uuid4(), query="", limit=5)
    except ValidationError:
        return
    raise AssertionError("Expected ValidationError")
