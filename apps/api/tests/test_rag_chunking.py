import json

import pytest

from app.domain.rag.chunking import ExtractedDocument, ExtractedPage, chunk_document


def test_chunk_document_keeps_citation_metadata() -> None:
    document = ExtractedDocument(
        source_id="source-1",
        filename="lesson.md",
        pages=[
            ExtractedPage(page_number=1, text="alpha beta gamma " * 120),
            ExtractedPage(page_number=2, text="delta epsilon zeta " * 120),
        ],
    )

    chunks = chunk_document(document, max_chars=300, overlap_chars=40)

    assert len(chunks) > 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].citation["filename"] == "lesson.md"
    assert chunks[0].citation["page_start"] == 1
    assert chunks[-1].citation["page_end"] == 2
    assert chunks[0].token_count > 0


def test_chunk_document_uses_stable_citation_metadata() -> None:
    document = ExtractedDocument(
        source_id="source-1",
        filename="lesson.md",
        pages=[ExtractedPage(page_number=1, text="alpha beta gamma " * 40)],
    )

    chunk = chunk_document(document, max_chars=100, overlap_chars=10)[0]

    assert chunk.citation["filename"] == "lesson.md"
    assert chunk.citation.to_dict() == {
        "source_id": "source-1",
        "filename": "lesson.md",
        "page_start": 1,
        "page_end": 1,
    }
    with pytest.raises(TypeError):
        chunk.citation["filename"] = "changed"


def test_chunk_payload_serializes_for_source_chunk_persistence() -> None:
    document = ExtractedDocument(
        source_id="source-1",
        filename="lesson.md",
        pages=[ExtractedPage(page_number=1, text="alpha beta gamma " * 20)],
    )

    chunk = chunk_document(document, max_chars=100, overlap_chars=10)[0]
    payload = chunk.to_source_chunk_payload()

    assert payload == {
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "citation": {
            "source_id": "source-1",
            "filename": "lesson.md",
            "page_start": 1,
            "page_end": 1,
        },
    }
    assert isinstance(payload, dict)
    assert isinstance(payload["citation"], dict)
    json.dumps(payload["citation"])


def test_chunk_document_respects_boundaries_and_page_citations() -> None:
    repeated = "same words repeat " * 12
    document = ExtractedDocument(
        source_id="source-1",
        filename="lesson.md",
        pages=[
            ExtractedPage(page_number=1, text=repeated),
            ExtractedPage(page_number=2, text=repeated),
        ],
    )

    chunks = chunk_document(document, max_chars=90, overlap_chars=12)

    assert chunks
    assert all(chunk.text for chunk in chunks)
    assert all(len(chunk.text) <= 90 for chunk in chunks)
    assert chunks[0].citation["page_start"] == 1
    assert chunks[0].citation["page_end"] == 1
    assert chunks[-1].citation["page_start"] == 2
    assert chunks[-1].citation["page_end"] == 2
    assert any(chunk.citation["page_start"] == 2 for chunk in chunks)


def test_chunk_document_rejects_invalid_overlap() -> None:
    document = ExtractedDocument(
        source_id="source-1",
        filename="lesson.md",
        pages=[ExtractedPage(page_number=1, text="short text")],
    )

    with pytest.raises(ValueError, match="overlap"):
        chunk_document(document, max_chars=100, overlap_chars=100)
