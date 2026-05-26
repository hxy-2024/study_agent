import uuid
from dataclasses import dataclass

from sqlalchemy import delete
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
) -> IngestionResult:
    source = await session.get(Source, source_id)
    if source is None:
        raise ValueError("Source not found")

    allowed_statuses = {
        SourceStatus.uploaded,
        SourceStatus.failed,
        SourceStatus.ready,
    }
    if source.status not in allowed_statuses:
        raise ValueError(f"Source status does not allow ingestion: {source.status.value}")
    if embedding_provider.dimension != 16:
        raise ValueError("Embedding dimension must be 16")

    tenant_id = source.tenant_id
    study_space_id = source.study_space_id
    object_key = source.object_key
    filename = source.filename

    job = IngestionJob(
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        source_id=source_id,
        status=IngestionJobStatus.running,
    )
    session.add(job)
    source.status = SourceStatus.processing
    source.error_message = None

    try:
        await session.flush()

        text = await reader.read_text(object_key)
        document = ExtractedDocument(
            source_id=str(source_id),
            filename=filename,
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
            chunk_rows.append(
                SourceChunk(
                    tenant_id=tenant_id,
                    study_space_id=study_space_id,
                    source_id=source_id,
                    chunk_index=payload["chunk_index"],
                    text=payload["text"],
                    token_count=payload["token_count"],
                    citation=payload["citation"],
                    embedding=embedding_provider.embed_text(chunk.text),
                    is_active=True,
                )
            )

        await session.execute(delete(SourceChunk).where(SourceChunk.source_id == source_id))
        session.add_all(chunk_rows)

        job.status = IngestionJobStatus.completed
        job.chunk_count = len(chunks)
        job.error_message = None
        source.status = SourceStatus.ready
        source.error_message = None
        await session.commit()
        await session.refresh(job)
        await session.refresh(source)
        return IngestionResult(
            job_id=job.id,
            source_id=source_id,
            status=job.status,
            chunk_count=job.chunk_count,
        )
    except Exception as exc:
        await session.rollback()
        await _persist_failed_ingestion(
            session=session,
            source_id=source_id,
            tenant_id=tenant_id,
            study_space_id=study_space_id,
            error_message=str(exc),
        )
        raise


async def _persist_failed_ingestion(
    session: AsyncSession,
    source_id: uuid.UUID,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    error_message: str,
) -> None:
    failed_source = await session.get(Source, source_id)
    if failed_source is not None:
        failed_source.status = SourceStatus.failed
        failed_source.error_message = error_message

    session.add(
        IngestionJob(
            tenant_id=tenant_id,
            study_space_id=study_space_id,
            source_id=source_id,
            status=IngestionJobStatus.failed,
            error_message=error_message,
        )
    )
    await session.commit()
