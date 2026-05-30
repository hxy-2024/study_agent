import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source, SourceChunk, SourceStatus, StudySpace
from app.domain.sources.schemas import TextSourceCreateRequest, UploadPresignRequest
from app.infrastructure.storage import TextSourceWriter, create_presigned_put_url

SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
    "text/markdown",
}
TEXT_CREATE_CONTENT_TYPES = {"text/plain", "text/markdown"}


def validate_content_type(content_type: str) -> None:
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}")


def slugify_filename(filename: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", filename.strip()).strip("-")
    return cleaned or "source"


def build_object_key(tenant_id: uuid.UUID, study_space_id: uuid.UUID, filename: str) -> str:
    source_id = uuid.uuid4()
    safe_name = slugify_filename(filename)
    return f"tenants/{tenant_id}/spaces/{study_space_id}/sources/{source_id}/{safe_name}"


async def ensure_study_space_in_tenant(
    session: AsyncSession,
    study_space_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> StudySpace:
    study_space = await session.scalar(
        select(StudySpace).where(
            StudySpace.id == study_space_id,
            StudySpace.tenant_id == tenant_id,
        )
    )
    if study_space is None:
        raise ValueError("Study space not found for tenant")
    return study_space


async def create_upload_request(
    session: AsyncSession,
    payload: UploadPresignRequest,
    tenant_id: uuid.UUID,
) -> tuple[Source, str]:
    validate_content_type(payload.content_type)
    await ensure_study_space_in_tenant(session, payload.study_space_id, tenant_id)
    object_key = build_object_key(tenant_id, payload.study_space_id, payload.filename)
    source = Source(
        tenant_id=tenant_id,
        study_space_id=payload.study_space_id,
        filename=payload.filename,
        content_type=payload.content_type,
        object_key=object_key,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    upload_url = create_presigned_put_url(object_key=object_key, content_type=payload.content_type)
    return source, upload_url


async def create_text_source(
    session: AsyncSession,
    payload: TextSourceCreateRequest,
    tenant_id: uuid.UUID,
    writer: TextSourceWriter,
) -> Source:
    if payload.content_type not in TEXT_CREATE_CONTENT_TYPES:
        raise ValueError("Pasted sources support only text/plain and text/markdown")
    await ensure_study_space_in_tenant(session, payload.study_space_id, tenant_id)
    object_key = build_object_key(tenant_id, payload.study_space_id, payload.filename)
    await writer.write_text(
        object_key=object_key,
        content=payload.content,
        content_type=payload.content_type,
    )
    source = Source(
        tenant_id=tenant_id,
        study_space_id=payload.study_space_id,
        filename=payload.filename,
        content_type=payload.content_type,
        object_key=object_key,
        status=SourceStatus.uploaded,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def get_source_for_tenant(
    session: AsyncSession,
    source_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Source:
    source = await session.scalar(
        select(Source).where(
            Source.id == source_id,
            Source.tenant_id == tenant_id,
        )
    )
    if source is None:
        raise ValueError("Source not found for tenant")
    return source


async def list_sources_for_space(
    session: AsyncSession,
    study_space_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[Source]:
    await ensure_study_space_in_tenant(session, study_space_id, tenant_id)
    result = await session.scalars(
        select(Source)
        .where(
            Source.tenant_id == tenant_id,
            Source.study_space_id == study_space_id,
        )
        .order_by(Source.created_at.desc(), Source.id)
    )
    return list(result.all())


async def mark_source_uploaded(
    session: AsyncSession,
    source_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Source:
    source = await get_source_for_tenant(session, source_id, tenant_id)
    if source.status != SourceStatus.pending_upload:
        raise ValueError(f"Source cannot be marked uploaded from status {source.status.value}")
    source.status = SourceStatus.uploaded
    await session.commit()
    await session.refresh(source)
    return source


async def list_source_chunks(
    session: AsyncSession,
    source_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[SourceChunk]:
    await get_source_for_tenant(session, source_id, tenant_id)
    result = await session.scalars(
        select(SourceChunk)
        .where(
            SourceChunk.source_id == source_id,
            SourceChunk.tenant_id == tenant_id,
        )
        .order_by(SourceChunk.chunk_index)
    )
    return list(result.all())


async def get_source_chunk_detail(
    session: AsyncSession,
    source_id: uuid.UUID,
    chunk_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SourceChunk:
    await get_source_for_tenant(session, source_id, tenant_id)
    chunk = await session.scalar(
        select(SourceChunk).where(
            SourceChunk.id == chunk_id,
            SourceChunk.source_id == source_id,
            SourceChunk.tenant_id == tenant_id,
        )
    )
    if chunk is None:
        raise ValueError("Source chunk not found for tenant")
    return chunk
