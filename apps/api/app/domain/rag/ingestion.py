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
        SourceStatus.processing,
        SourceStatus.failed,
        SourceStatus.ready,
    }
    if source.status not in allowed_statuses:
        raise ValueError(f"Source status does not allow ingestion: {source.status.value}")

    job = IngestionJob(
        tenant_id=source.tenant_id,
        study_space_id=source.study_space_id,
        source_id=source.id,
        status=IngestionJobStatus.running,
    )
    session.add(job)
    source.status = SourceStatus.processing
    source.error_message = None
    await session.flush()

    try:
        text = await reader.read_text(source.object_key)
        document = ExtractedDocument(
            source_id=str(source.id),
            filename=source.filename,
            pages=[ExtractedPage(page_number=1, text=text)],
        )
        chunks = chunk_document(
            document,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        )

        await session.execute(delete(SourceChunk).where(SourceChunk.source_id == source.id))
        for chunk in chunks:
            payload = chunk.to_source_chunk_payload()
            session.add(
                SourceChunk(
                    tenant_id=source.tenant_id,
                    study_space_id=source.study_space_id,
                    source_id=source.id,
                    chunk_index=payload["chunk_index"],
                    text=payload["text"],
                    token_count=payload["token_count"],
                    citation=payload["citation"],
                    embedding=embedding_provider.embed_text(chunk.text),
                    is_active=True,
                )
            )

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
            source_id=source.id,
            status=job.status,
            chunk_count=job.chunk_count,
        )
    except Exception as exc:
        error_message = str(exc)
        job.status = IngestionJobStatus.failed
        job.error_message = error_message
        source.status = SourceStatus.failed
        source.error_message = error_message
        await session.commit()
        raise
