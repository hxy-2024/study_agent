import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chapter, ChapterStatus, LearningRoute, Source, SourceChunk, StudySpace
from app.domain.chapter_study.schemas import (
    ChapterEvidenceResponse,
    ChapterStudyChapterResponse,
    ChapterStudyDetailResponse,
    ChapterStudyRouteResponse,
    ChapterStudySpaceResponse,
)


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def chapter_response(chapter) -> ChapterStudyChapterResponse:
    return ChapterStudyChapterResponse(
        id=chapter.id,
        study_space_id=chapter.study_space_id,
        learning_route_id=chapter.learning_route_id,
        order_index=chapter.order_index,
        title=chapter.title,
        goal=chapter.goal,
        summary=chapter.summary,
        estimated_days=chapter.estimated_days,
        status=_enum_value(chapter.status),
        source_chunk_refs=chapter.source_chunk_refs,
    )


def route_response(route) -> ChapterStudyRouteResponse:
    return ChapterStudyRouteResponse(
        id=route.id,
        study_space_id=route.study_space_id,
        version=route.version,
        status=_enum_value(route.status),
        title=route.title,
    )


def study_space_response(study_space) -> ChapterStudySpaceResponse:
    return ChapterStudySpaceResponse(id=study_space.id, name=study_space.name)


def evidence_response(chunk, source, max_chars: int = 700) -> ChapterEvidenceResponse:
    return ChapterEvidenceResponse(
        source_id=chunk.source_id,
        chunk_id=chunk.id,
        chunk_index=chunk.chunk_index,
        source_filename=source.filename,
        text=chunk.text[:max_chars],
        citation=chunk.citation or {},
    )


def referenced_chunk_ids(source_chunk_refs: Iterable[dict]) -> list[uuid.UUID]:
    chunk_ids: list[uuid.UUID] = []
    for ref in source_chunk_refs:
        raw_id = ref.get("chunk_id")
        if raw_id is None:
            continue
        try:
            chunk_ids.append(uuid.UUID(str(raw_id)))
        except ValueError:
            continue
    return chunk_ids


def find_next_chapter(chapter, route_chapters: list) -> object | None:
    candidates = [
        candidate
        for candidate in route_chapters
        if candidate.order_index > chapter.order_index and candidate.status != ChapterStatus.completed
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: candidate.order_index)


def build_chapter_detail(
    chapter,
    route,
    study_space,
    evidence: list[ChapterEvidenceResponse],
    route_chapters: list,
) -> ChapterStudyDetailResponse:
    next_chapter = find_next_chapter(chapter, route_chapters)
    return ChapterStudyDetailResponse(
        chapter=chapter_response(chapter),
        route=route_response(route),
        study_space=study_space_response(study_space),
        evidence=evidence,
        next_chapter_id=getattr(next_chapter, "id", None),
    )


async def load_chapter_evidence(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter: Chapter,
) -> list[ChapterEvidenceResponse]:
    chunk_ids = referenced_chunk_ids(chapter.source_chunk_refs)
    if not chunk_ids:
        return []

    rows = await session.execute(
        select(SourceChunk, Source)
        .join(Source, Source.id == SourceChunk.source_id)
        .where(
            SourceChunk.id.in_(chunk_ids),
            SourceChunk.tenant_id == tenant_id,
            SourceChunk.study_space_id == chapter.study_space_id,
            SourceChunk.is_active.is_(True),
            Source.tenant_id == tenant_id,
            Source.study_space_id == chapter.study_space_id,
        )
        .order_by(SourceChunk.chunk_index)
    )
    return [evidence_response(chunk=chunk, source=source) for chunk, source in rows.all()]


async def load_chapter_context(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> tuple[Chapter, LearningRoute, StudySpace, list[Chapter], list[ChapterEvidenceResponse]]:
    chapter = await session.scalar(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.tenant_id == tenant_id,
        )
    )
    if chapter is None:
        raise ValueError("Chapter not found for tenant")

    route = await session.scalar(
        select(LearningRoute).where(
            LearningRoute.id == chapter.learning_route_id,
            LearningRoute.tenant_id == tenant_id,
        )
    )
    if route is None:
        raise ValueError("Route not found for tenant")

    study_space = await session.scalar(
        select(StudySpace).where(
            StudySpace.id == chapter.study_space_id,
            StudySpace.tenant_id == tenant_id,
        )
    )
    if study_space is None:
        raise ValueError("Study space not found for tenant")

    route_chapters_rows = await session.scalars(
        select(Chapter)
        .where(
            Chapter.tenant_id == tenant_id,
            Chapter.learning_route_id == chapter.learning_route_id,
        )
        .order_by(Chapter.order_index)
    )
    route_chapters = list(route_chapters_rows)
    evidence = await load_chapter_evidence(session=session, tenant_id=tenant_id, chapter=chapter)
    return chapter, route, study_space, route_chapters, evidence


async def get_chapter_detail(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> ChapterStudyDetailResponse:
    chapter, route, study_space, route_chapters, evidence = await load_chapter_context(
        session=session,
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )
    return build_chapter_detail(
        chapter=chapter,
        route=route,
        study_space=study_space,
        evidence=evidence,
        route_chapters=route_chapters,
    )


async def complete_chapter(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> ChapterStudyDetailResponse:
    chapter, route, study_space, route_chapters, evidence = await load_chapter_context(
        session=session,
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )
    if chapter.status != ChapterStatus.completed:
        chapter.status = ChapterStatus.completed
        next_chapter = find_next_chapter(chapter, route_chapters)
        if next_chapter is not None:
            next_chapter.status = ChapterStatus.active
        await session.commit()

    return build_chapter_detail(
        chapter=chapter,
        route=route,
        study_space=study_space,
        evidence=evidence,
        route_chapters=route_chapters,
    )
