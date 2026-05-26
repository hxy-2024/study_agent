import os
import uuid

import pytest
from sqlalchemy import select
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

    source_id = None
    async with session_factory() as session:
        source = await _create_source(session, status=SourceStatus.uploaded)
        source_id = source.id
        session.add(
            SourceChunk(
                tenant_id=source.tenant_id,
                study_space_id=source.study_space_id,
                source_id=source.id,
                chunk_index=0,
                text="old chunk text",
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
        chunks = (
            await session.execute(
                select(SourceChunk)
                .where(SourceChunk.source_id == source.id)
                .order_by(SourceChunk.chunk_index)
            )
        ).scalars().all()

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

    async with session_factory() as session:
        source = await _create_source(session, status=SourceStatus.uploaded)
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

    await engine.dispose()

    assert source.status == SourceStatus.failed
    assert source.error_message == "storage unavailable"
    assert len(jobs) == 1
    assert jobs[0].status == IngestionJobStatus.failed
    assert jobs[0].error_message == "storage unavailable"


class FailingTextSourceReader(TextSourceReader):
    async def read_text(self, object_key: str) -> str:
        raise RuntimeError("storage unavailable")


async def _create_source(session, status: SourceStatus) -> Source:
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
    return source
