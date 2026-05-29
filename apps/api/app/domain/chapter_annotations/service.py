import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chapter, ChapterAnnotation, ChapterAnnotationKind, SourceChunk
from app.domain.chapter_annotations.schemas import (
    ChapterAnnotationCreateRequest,
    ChapterAnnotationUpdateRequest,
)


async def ensure_chapter_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> Chapter:
    chapter = await session.scalar(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.tenant_id == tenant_id,
        )
    )
    if chapter is None:
        raise ValueError("Chapter not found for tenant")
    return chapter


async def ensure_source_chunk_for_chapter(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    source_chunk_id: uuid.UUID | None,
) -> None:
    if source_chunk_id is None:
        return
    source_chunk = await session.scalar(
        select(SourceChunk).where(
            SourceChunk.id == source_chunk_id,
            SourceChunk.tenant_id == tenant_id,
            SourceChunk.study_space_id == study_space_id,
            SourceChunk.is_active.is_(True),
        )
    )
    if source_chunk is None:
        raise ValueError("Source chunk not found for tenant")


async def list_chapter_annotations(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> list[ChapterAnnotation]:
    await ensure_chapter_for_tenant(session, tenant_id, chapter_id)
    result = await session.scalars(
        select(ChapterAnnotation)
        .where(
            ChapterAnnotation.tenant_id == tenant_id,
            ChapterAnnotation.chapter_id == chapter_id,
        )
        .order_by(ChapterAnnotation.created_at.desc(), ChapterAnnotation.id)
    )
    return list(result.all())


async def create_chapter_annotation(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    chapter_id: uuid.UUID,
    payload: ChapterAnnotationCreateRequest,
) -> ChapterAnnotation:
    chapter = await ensure_chapter_for_tenant(session, tenant_id, chapter_id)
    await ensure_source_chunk_for_chapter(session, tenant_id, chapter.study_space_id, payload.source_chunk_id)
    annotation = ChapterAnnotation(
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=chapter.study_space_id,
        chapter_id=chapter_id,
        source_chunk_id=payload.source_chunk_id,
        kind=ChapterAnnotationKind(payload.kind),
        content=payload.content.strip() if payload.content else None,
        quote=payload.quote.strip() if payload.quote else None,
        anchor=payload.anchor,
    )
    session.add(annotation)
    await session.commit()
    await session.refresh(annotation)
    return annotation


async def get_annotation_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    annotation_id: uuid.UUID,
) -> ChapterAnnotation:
    annotation = await session.scalar(
        select(ChapterAnnotation).where(
            ChapterAnnotation.id == annotation_id,
            ChapterAnnotation.tenant_id == tenant_id,
        )
    )
    if annotation is None:
        raise ValueError("Chapter annotation not found for tenant")
    return annotation


async def update_chapter_annotation(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    annotation_id: uuid.UUID,
    payload: ChapterAnnotationUpdateRequest,
) -> ChapterAnnotation:
    annotation = await get_annotation_for_tenant(session, tenant_id, annotation_id)
    if payload.content is not None:
        annotation.content = payload.content.strip() or None
    if payload.quote is not None:
        annotation.quote = payload.quote.strip() or None
    if payload.anchor is not None:
        annotation.anchor = payload.anchor
    await session.commit()
    await session.refresh(annotation)
    return annotation


async def delete_chapter_annotation(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    annotation_id: uuid.UUID,
) -> None:
    annotation = await get_annotation_for_tenant(session, tenant_id, annotation_id)
    await session.delete(annotation)
    await session.commit()
