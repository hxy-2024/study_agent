from app.db.models import IngestionJob, IngestionJobStatus, SourceChunk
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.ingestion import InMemoryTextSourceReader

import pytest


def test_rag_models_are_importable() -> None:
    assert IngestionJob.__tablename__ == "ingestion_jobs"
    assert SourceChunk.__tablename__ == "source_chunks"
    assert IngestionJobStatus.pending.value == "pending"


@pytest.mark.anyio
async def test_in_memory_text_source_reader_reads_known_object() -> None:
    reader = InMemoryTextSourceReader({"objects/intro.md": "hello"})

    assert await reader.read_text("objects/intro.md") == "hello"


def test_deterministic_embedding_provider_is_usable_by_ingestion() -> None:
    provider = DeterministicEmbeddingProvider(dimension=16)

    assert len(provider.embed_text("chapter content")) == 16
