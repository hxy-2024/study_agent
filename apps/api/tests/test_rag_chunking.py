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


def test_chunk_document_rejects_invalid_overlap() -> None:
    document = ExtractedDocument(
        source_id="source-1",
        filename="lesson.md",
        pages=[ExtractedPage(page_number=1, text="short text")],
    )

    try:
        chunk_document(document, max_chars=100, overlap_chars=100)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
