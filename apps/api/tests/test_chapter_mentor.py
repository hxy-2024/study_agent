import uuid

from app.domain.chapter_mentor.service import compose_grounded_answer
from app.domain.rag.retrieval import RetrievedChunk


def retrieved_chunk(
    text: str,
    *,
    chunk_index: int = 0,
    source_id: uuid.UUID | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        source_id=source_id or uuid.uuid4(),
        chunk_index=chunk_index,
        text=text,
        citation={"page_number": 2},
        embedding=[0.1] * 16,
        score=0.9,
    )


def test_compose_grounded_answer_uses_retrieved_chunks() -> None:
    chunks = [
        retrieved_chunk("Embeddings convert text into vectors for semantic search."),
        retrieved_chunk("RAG retrieves relevant evidence before generating an answer.", chunk_index=1),
    ]

    response = compose_grounded_answer(
        question="How does RAG work?",
        chunks=chunks,
        source_filenames={chunks[0].source_id: "vectors.md", chunks[1].source_id: "rag.md"},
    )

    assert response.question == "How does RAG work?"
    assert "RAG retrieves relevant evidence" in response.answer
    assert len(response.citations) == 2
    assert response.citations[0].source_filename == "vectors.md"


def test_compose_grounded_answer_handles_empty_retrieval() -> None:
    response = compose_grounded_answer(
        question="What should I study?",
        chunks=[],
        source_filenames={},
    )

    assert "could not find enough source material" in response.answer
    assert response.citations == []
