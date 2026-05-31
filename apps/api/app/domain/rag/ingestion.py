import uuid
from dataclasses import dataclass

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IngestionJob, IngestionJobStatus, Source, SourceChunk, SourceStatus
from app.domain.rag.chunking import ExtractedDocument, ExtractedPage, chunk_document
from app.domain.rag.embeddings import EmbeddingProvider
from app.infrastructure.storage import TextSourceReader


class InMemoryTextSourceReader(TextSourceReader):
    def __init__(self, objects: dict[str, str]) -> None:
        self._objects = objects

    async def read_text(self, object_key: str) -> str:
        try:
            return self._objects[object_key]
        except KeyError as exc:
            raise FileNotFoundError(object_key) from exc


@dataclass(frozen=True)
class IngestionResult:
    job_id: uuid.UUID
    source_id: uuid.UUID
    status: IngestionJobStatus
    chunk_count: int


async def ingest_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    reader: TextSourceReader,
    embedding_provider: EmbeddingProvider,
    max_chars: int,
    overlap_chars: int,
    tenant_id: uuid.UUID | None = None,
) -> IngestionResult:
    source = await session.get(Source, source_id)
    if source is None:
        raise ValueError("Source not found")
    validate_source_for_ingestion(source=source, tenant_id=tenant_id)

    allowed_statuses = {
        SourceStatus.uploaded,
        SourceStatus.failed,
        SourceStatus.ready,
    }
    if source.status not in allowed_statuses:
        raise ValueError(f"Source status does not allow ingestion: {source.status.value}")
    claim = await _claim_source_for_ingestion(
        session=session,
        source=source,
        allowed_statuses=allowed_statuses,
        tenant_id=tenant_id,
    )
    job_id = claim.job_id
    chunk_count = 0

    try:
        text = await reader.read_text(claim.object_key)
        document = ExtractedDocument(
            source_id=str(source_id),
            filename=claim.filename,
            pages=[ExtractedPage(page_number=1, text=text)],
        )
        chunks = chunk_document(
            document,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        )
        chunk_rows = []
        for chunk in chunks:
            payload = chunk.to_source_chunk_payload()
            embedding = embedding_provider.embed_text(chunk.text)
            chunk_rows.append(
                SourceChunk(
                    tenant_id=claim.tenant_id,
                    study_space_id=claim.study_space_id,
                    source_id=source_id,
                    chunk_index=payload["chunk_index"],
                    text=payload["text"],
                    token_count=payload["token_count"],
                    citation=payload["citation"],
                    embedding=embedding,
                    embedding_provider=embedding_provider.provider_key,
                    embedding_model=embedding_provider.model_name,
                    embedding_dimension=len(embedding),
                    is_active=True,
                )
            )

        await session.execute(delete(SourceChunk).where(SourceChunk.source_id == source_id))
        session.add_all(chunk_rows)

        job = await session.get(IngestionJob, job_id)
        source = await session.get(Source, source_id)
        if job is None or source is None:
            raise ValueError("Ingestion state not found")

        chunk_count = len(chunks)
        job.status = IngestionJobStatus.completed
        job.chunk_count = chunk_count
        job.error_message = None
        source.status = SourceStatus.ready
        source.error_message = None
        await session.commit()
    except Exception as exc:
        await session.rollback()
        await _persist_failed_ingestion(
            session=session,
            source_id=source_id,
            job_id=job_id,
            error_message=str(exc),
        )
        raise

    return IngestionResult(
        job_id=job_id,
        source_id=source_id,
        status=IngestionJobStatus.completed,
        chunk_count=chunk_count,
    )


def validate_source_for_ingestion(source: Source, tenant_id: uuid.UUID | None) -> None:
    if tenant_id is not None and source.tenant_id != tenant_id:
        raise ValueError("Source not found for tenant")


@dataclass(frozen=True)
class _IngestionClaim:
    job_id: uuid.UUID
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    object_key: str
    filename: str


async def _claim_source_for_ingestion(
    session: AsyncSession,
    source: Source,
    allowed_statuses: set[SourceStatus],
    tenant_id: uuid.UUID | None,
) -> _IngestionClaim:
    source_tenant_id = source.tenant_id
    study_space_id = source.study_space_id
    object_key = source.object_key
    filename = source.filename

    claim_conditions = [Source.id == source.id, Source.status.in_(allowed_statuses)]
    if tenant_id is not None:
        claim_conditions.append(Source.tenant_id == tenant_id)

    result = await session.execute(
        update(Source)
        .where(*claim_conditions)
        .values(status=SourceStatus.processing, error_message=None)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        await session.rollback()
        raise ValueError("Source is already processing")

    job = IngestionJob(
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        source_id=source.id,
        status=IngestionJobStatus.running,
    )
    session.add(job)
    await session.flush()
    job_id = job.id
    await session.commit()

    return _IngestionClaim(
        job_id=job_id,
        tenant_id=source_tenant_id,
        study_space_id=study_space_id,
        object_key=object_key,
        filename=filename,
    )


async def _persist_failed_ingestion(
    session: AsyncSession,
    source_id: uuid.UUID,
    job_id: uuid.UUID,
    error_message: str,
) -> None:
    failed_source = await session.get(Source, source_id)
    if failed_source is not None:
        failed_source.status = SourceStatus.failed
        failed_source.error_message = error_message

    failed_job = await session.get(IngestionJob, job_id)
    if failed_job is not None:
        failed_job.status = IngestionJobStatus.failed
        failed_job.error_message = error_message
    await session.commit()
