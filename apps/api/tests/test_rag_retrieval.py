import uuid

from app.domain.rag.retrieval import RetrievedChunk, rank_chunks_by_dot_product


def test_rank_chunks_by_dot_product_orders_relevant_chunks() -> None:
    tenant_id = uuid.uuid4()
    space_id = uuid.uuid4()
    chunks = [
        RetrievedChunk(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            study_space_id=space_id,
            source_id=uuid.uuid4(),
            chunk_index=0,
            text="unrelated cooking note",
            citation={"filename": "a.md"},
            embedding=[1.0, 0.0],
            score=0.0,
        ),
        RetrievedChunk(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            study_space_id=space_id,
            source_id=uuid.uuid4(),
            chunk_index=1,
            text="gradient descent learning rate",
            citation={"filename": "b.md"},
            embedding=[0.0, 1.0],
            score=0.0,
        ),
    ]

    ranked = rank_chunks_by_dot_product(query_embedding=[0.0, 1.0], chunks=chunks, limit=1)

    assert ranked[0].text == "gradient descent learning rate"
    assert ranked[0].score == 1.0
