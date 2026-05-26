import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Source, SourceStatus, StudySpace, Tenant, User
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.ingestion import InMemoryTextSourceReader, ingest_source


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Postgres integration tests require RUN_POSTGRES_TESTS=1 and DATABASE_URL",
)


@pytest.mark.anyio
async def test_ingest_source_persists_chunks_and_marks_source_ready() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        tenant = Tenant(name="RAG Test Tenant")
        user = User(
            email=f"rag-test-{uuid.uuid4()}@example.com",
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
            object_key=f"objects/{uuid.uuid4()}/intro.md",
            status=SourceStatus.uploaded,
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)

        result = await ingest_source(
            session=session,
            source_id=source.id,
            reader=InMemoryTextSourceReader(
                {source.object_key: "Chapter one content with enough words to produce a chunk."}
            ),
            embedding_provider=DeterministicEmbeddingProvider(16),
            max_chars=200,
            overlap_chars=20,
        )

        await session.refresh(source)

    await engine.dispose()

    assert result.status.value == "completed"
    assert result.chunk_count > 0
    assert source.status == SourceStatus.ready
