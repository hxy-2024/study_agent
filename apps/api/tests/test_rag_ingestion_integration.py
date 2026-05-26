import os
import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    IngestionJob,
    IngestionJobStatus,
    Source,
    SourceChunk,
    SourceStatus,
    StudySpace,
    Tenant,
    User,
)
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.ingestion import InMemoryTextSourceReader, ingest_source
from app.infrastructure.storage import TextSourceReader


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Postgres integration tests require RUN_POSTGRES_TESTS=1 and DATABASE_URL",
)


@pytest.mark.anyio
async def test_ingest_source_replaces_chunks_and_marks_source_ready() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    rows = None
    source_id = None
    try:
        async with session_factory() as session:
            rows = await _create_source(session, status=SourceStatus.uploaded)
            source = rows.source
            source_id = source.id
            await _add_existing_chunk(session, source, text="old chunk text")
            await session.commit()

            result = await ingest_source(
                session=session,
                source_id=source.id,
                reader=InMemoryTextSourceReader(
                    {
                        source.object_key: (
                            "Chapter one content with enough words to produce a replacement chunk."
                        )
                    }
                ),
                embedding_provider=DeterministicEmbeddingProvider(16),
                max_chars=200,
                overlap_chars=20,
            )

            await session.refresh(source)
            jobs = (
                await session.execute(
                    select(IngestionJob).where(IngestionJob.source_id == source.id)
                )
            ).scalars().all()
            chunks = await _source_chunks(session, source.id)
    finally:
        if rows is not None:
            async with session_factory() as cleanup_session:
                await _cleanup_rows(cleanup_session, rows)
        await engine.dispose()

    assert result.status == IngestionJobStatus.completed
    assert result.chunk_count > 0
    assert len(jobs) == 1
    assert jobs[0].status == IngestionJobStatus.completed
    assert jobs[0].chunk_count == result.chunk_count
    assert source.status == SourceStatus.ready
    assert len(chunks) == result.chunk_count
    assert all(chunk.text != "old chunk text" for chunk in chunks)
    assert chunks[0].citation == {
        "source_id": str(source_id),
        "filename": "intro.md",
        "page_start": 1,
        "page_end": 1,
    }
    assert type(chunks[0].citation) is dict
    assert len(chunks[0].embedding) == 16


@pytest.mark.anyio
async def test_ingest_source_marks_job_and_source_failed_when_read_fails() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    rows = None
    try:
        async with session_factory() as session:
            rows = await _create_source(session, status=SourceStatus.uploaded)
            source = rows.source
            await session.commit()

            with pytest.raises(RuntimeError, match="storage unavailable"):
                await ingest_source(
                    session=session,
                    source_id=source.id,
                    reader=FailingTextSourceReader(),
                    embedding_provider=DeterministicEmbeddingProvider(16),
                    max_chars=200,
                    overlap_chars=20,
                )

            await session.refresh(source)
            jobs = (
                await session.execute(
                    select(IngestionJob).where(IngestionJob.source_id == source.id)
                )
            ).scalars().all()
    finally:
        if rows is not None:
            async with session_factory() as cleanup_session:
                await _cleanup_rows(cleanup_session, rows)
        await engine.dispose()

    assert source.status == SourceStatus.failed
    assert source.error_message == "storage unavailable"
    assert len(jobs) == 1
    assert jobs[0].status == IngestionJobStatus.failed
    assert jobs[0].error_message == "storage unavailable"


@pytest.mark.anyio
async def test_ingest_source_keeps_existing_chunks_when_embedding_fails() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    rows = None
    try:
        async with session_factory() as session:
            rows = await _create_source(session, status=SourceStatus.ready)
            source = rows.source
            await _add_existing_chunk(session, source, text="old chunk survives")
            await session.commit()

            with pytest.raises(RuntimeError, match="embedding unavailable"):
                await ingest_source(
                    session=session,
                    source_id=source.id,
                    reader=InMemoryTextSourceReader(
                        {source.object_key: "New content that should not replace old chunks."}
                    ),
                    embedding_provider=FailingEmbeddingProvider(),
                    max_chars=200,
                    overlap_chars=20,
                )

            await session.refresh(source)
            jobs = (
                await session.execute(
                    select(IngestionJob).where(IngestionJob.source_id == source.id)
                )
            ).scalars().all()
            chunks = await _source_chunks(session, source.id)
    finally:
        if rows is not None:
            async with session_factory() as cleanup_session:
                await _cleanup_rows(cleanup_session, rows)
        await engine.dispose()

    assert source.status == SourceStatus.failed
    assert source.error_message == "embedding unavailable"
    assert len(jobs) == 1
    assert jobs[0].status == IngestionJobStatus.failed
    assert jobs[0].error_message == "embedding unavailable"
    assert len(chunks) == 1
    assert chunks[0].text == "old chunk survives"


@pytest.mark.anyio
async def test_ingest_source_commits_processing_before_reading_text() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    rows = None
    reader = None
    try:
        async with session_factory() as session:
            rows = await _create_source(session, status=SourceStatus.ready)
            source = rows.source
            await session.commit()
            reader = StatusInspectingTextSourceReader(
                session_factory=session_factory,
                source_id=source.id,
                text="Content read after processing status commits.",
            )

            await ingest_source(
                session=session,
                source_id=source.id,
                reader=reader,
                embedding_provider=DeterministicEmbeddingProvider(16),
                max_chars=200,
                overlap_chars=20,
            )
    finally:
        if rows is not None:
            async with session_factory() as cleanup_session:
                await _cleanup_rows(cleanup_session, rows)
        await engine.dispose()

    assert reader is not None
    assert reader.observed_status == SourceStatus.processing


class FailingTextSourceReader(TextSourceReader):
    async def read_text(self, object_key: str) -> str:
        raise RuntimeError("storage unavailable")


class FailingEmbeddingProvider(DeterministicEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__(dimension=16)

    def embed_text(self, text: str) -> list[float]:
        raise RuntimeError("embedding unavailable")


class StatusInspectingTextSourceReader(TextSourceReader):
    def __init__(self, session_factory, source_id: uuid.UUID, text: str) -> None:
        self._session_factory = session_factory
        self._source_id = source_id
        self._text = text
        self.observed_status: SourceStatus | None = None

    async def read_text(self, object_key: str) -> str:
        async with self._session_factory() as session:
            source = await session.get(Source, self._source_id)
            assert source is not None
            self.observed_status = source.status
        return self._text


@dataclass(frozen=True)
class CreatedRows:
    tenant: Tenant
    user: User
    study_space: StudySpace
    source: Source


async def _create_source(session, status: SourceStatus) -> CreatedRows:
    unique_id = uuid.uuid4()
    tenant = Tenant(name=f"RAG Test Tenant {unique_id}")
    user = User(
        email=f"rag-test-{unique_id}@example.com",
        display_name="RAG Test User",
    )
    session.add_all([tenant, user])
    await session.flush()

    study_space = StudySpace(
        tenant_id=tenant.id,
        owner_user_id=user.id,
        name="RAG Test Space",
        goal="Learn ingestion",
    )
    session.add(study_space)
    await session.flush()

    source = Source(
        tenant_id=tenant.id,
        study_space_id=study_space.id,
        filename="intro.md",
        content_type="text/markdown",
        object_key=f"objects/{unique_id}/intro.md",
        status=status,
    )
    session.add(source)
    await session.flush()
    return CreatedRows(tenant=tenant, user=user, study_space=study_space, source=source)


async def _add_existing_chunk(session, source: Source, text: str) -> None:
    session.add(
        SourceChunk(
            tenant_id=source.tenant_id,
            study_space_id=source.study_space_id,
            source_id=source.id,
            chunk_index=0,
            text=text,
            token_count=3,
            citation={
                "source_id": str(source.id),
                "filename": "old.md",
                "page_start": 9,
                "page_end": 9,
            },
            embedding=[0.0] * 16,
            is_active=True,
        )
    )


async def _source_chunks(session, source_id: uuid.UUID) -> list[SourceChunk]:
    return (
        (
            await session.execute(
                select(SourceChunk)
                .where(SourceChunk.source_id == source_id)
                .order_by(SourceChunk.chunk_index)
            )
        )
        .scalars()
        .all()
    )


async def _cleanup_rows(session, rows: CreatedRows) -> None:
    await session.execute(delete(SourceChunk).where(SourceChunk.source_id == rows.source.id))
    await session.execute(delete(IngestionJob).where(IngestionJob.source_id == rows.source.id))
    await session.execute(delete(Source).where(Source.id == rows.source.id))
    await session.execute(delete(StudySpace).where(StudySpace.id == rows.study_space.id))
    await session.execute(delete(User).where(User.id == rows.user.id))
    await session.execute(delete(Tenant).where(Tenant.id == rows.tenant.id))
    await session.commit()
