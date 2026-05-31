import uuid

import pytest

from app.db.models import IngestionJob, IngestionJobStatus, Source, SourceChunk, SourceStatus
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.ingestion import (
    InMemoryTextSourceReader,
    ingest_source,
    validate_source_for_ingestion,
)


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


def test_validate_source_for_ingestion_rejects_tenant_mismatch() -> None:
    source = _source_with_status(SourceStatus.uploaded)

    with pytest.raises(ValueError, match="Source not found for tenant"):
        validate_source_for_ingestion(source=source, tenant_id=uuid.uuid4())


@pytest.mark.anyio
async def test_ingest_source_rejects_pending_upload_sources() -> None:
    source = Source(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        filename="intro.md",
        content_type="text/markdown",
        object_key="objects/intro.md",
        status=SourceStatus.pending_upload,
    )

    class FakeSession:
        async def get(self, model, object_id):
            assert model is Source
            assert object_id == source.id
            return source

    with pytest.raises(ValueError, match="pending_upload"):
        await ingest_source(
            session=FakeSession(),
            source_id=source.id,
            reader=InMemoryTextSourceReader({"objects/intro.md": "hello"}),
            embedding_provider=DeterministicEmbeddingProvider(16),
            max_chars=200,
            overlap_chars=20,
        )


@pytest.mark.anyio
async def test_ingest_source_rejects_processing_sources() -> None:
    source = _source_with_status(SourceStatus.processing)

    with pytest.raises(ValueError, match="processing"):
        await ingest_source(
            session=FakeSourceSession(source),
            source_id=source.id,
            reader=InMemoryTextSourceReader({"objects/intro.md": "hello"}),
            embedding_provider=DeterministicEmbeddingProvider(16),
            max_chars=200,
            overlap_chars=20,
        )


class FakeSourceSession:
    def __init__(self, source: Source) -> None:
        self.source = source
        self.write_attempted = False

    async def get(self, model, object_id):
        assert model is Source
        assert object_id == self.source.id
        return self.source

    def add(self, instance) -> None:
        self.write_attempted = True

    async def flush(self) -> None:
        self.write_attempted = True

    async def execute(self, statement) -> None:
        self.write_attempted = True

    async def commit(self) -> None:
        self.write_attempted = True


def _source_with_status(status: SourceStatus) -> Source:
    return Source(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        filename="intro.md",
        content_type="text/markdown",
        object_key="objects/intro.md",
        status=status,
    )
