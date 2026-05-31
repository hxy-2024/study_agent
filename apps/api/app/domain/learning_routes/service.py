import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Chapter,
    ChapterStatus,
    LearningRoute,
    LearningRouteStatus,
    SourceChunk,
    StudySpace,
)
from app.domain.learning_routes.generator import (
    RouteGenerationRequest,
    RouteGenerator,
    SourceChunkExcerpt,
)
from app.domain.rag.embeddings import EmbeddingProvider
from app.domain.rag.retrieval import RetrievedChunk, retrieve_chunks
from app.domain.sources.service import ensure_study_space_in_tenant


def collect_chunk_excerpts(
    chunks: list[SourceChunk] | list[RetrievedChunk],
    max_excerpt_chars: int,
) -> list[SourceChunkExcerpt]:
    return [
        SourceChunkExcerpt(
            source_id=chunk.source_id,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            text=chunk.text[:max_excerpt_chars],
        )
        for chunk in chunks
    ]


async def load_route_source_chunks(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    max_chunks: int = 24,
) -> list[SourceChunk]:
    rows = await session.scalars(
        select(SourceChunk)
        .where(
            SourceChunk.tenant_id == tenant_id,
            SourceChunk.study_space_id == study_space_id,
            SourceChunk.is_active.is_(True),
        )
        .order_by(SourceChunk.source_id, SourceChunk.chunk_index)
        .limit(max_chunks)
    )
    return list(rows)


async def load_relevant_route_chunks(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space: StudySpace,
    embedding_provider: EmbeddingProvider,
    max_chunks: int = 24,
) -> list[RetrievedChunk]:
    return await retrieve_chunks(
        session=session,
        tenant_id=tenant_id,
        study_space_id=study_space.id,
        query=f"{study_space.name}\n{study_space.goal}",
        limit=max_chunks,
        embedding_provider=embedding_provider,
    )


async def next_route_version(
    session: AsyncSession,
    study_space_id: uuid.UUID,
) -> int:
    current = await session.scalar(
        select(func.max(LearningRoute.version)).where(LearningRoute.study_space_id == study_space_id)
    )
    return int(current or 0) + 1


async def persist_generated_route(
    session,
    study_space: StudySpace,
    version: int,
    chunks: list[SourceChunk],
    generator: RouteGenerator,
    max_chapters: int,
    embedding_provider: EmbeddingProvider | None = None,
) -> tuple[LearningRoute, list[Chapter]]:
    excerpts = collect_chunk_excerpts(chunks, max_excerpt_chars=500)
    result = await generator.generate(
        RouteGenerationRequest(
            tenant_id=study_space.tenant_id,
            study_space_id=study_space.id,
            study_space_name=study_space.name,
            goal=study_space.goal,
            level=study_space.level,
            intensity=study_space.intensity,
            target_days=study_space.target_days,
            max_chapters=max_chapters,
            chunks=excerpts,
        )
    )
    if not result.chapters:
        raise ValueError("Route generation produced no chapters")

    route = LearningRoute(
        tenant_id=study_space.tenant_id,
        study_space_id=study_space.id,
        version=version,
        status=LearningRouteStatus.draft,
        title=result.title,
        summary=result.summary,
        generation_strategy=result.generation_strategy,
    )
    session.add(route)
    await session.flush()

    chapters = [
        Chapter(
            tenant_id=study_space.tenant_id,
            study_space_id=study_space.id,
            learning_route_id=route.id,
            order_index=index,
            title=chapter.title,
            goal=chapter.goal,
            summary=chapter.summary,
            estimated_days=chapter.estimated_days,
            status=ChapterStatus.not_started,
            source_chunk_refs=chapter.source_chunk_refs,
        )
        for index, chapter in enumerate(result.chapters, start=1)
    ]
    for chapter in chapters:
        session.add(chapter)
    await session.flush()
    return route, chapters


async def create_route_draft(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    generator: RouteGenerator,
    max_chapters: int,
    embedding_provider: EmbeddingProvider | None = None,
) -> tuple[LearningRoute, list[Chapter]]:
    for _attempt in range(2):
        try:
            study_space = await ensure_study_space_in_tenant(
                session=session,
                study_space_id=study_space_id,
                tenant_id=tenant_id,
            )
            chunks: list[SourceChunk] | list[RetrievedChunk]
            if embedding_provider is not None:
                chunks = await load_relevant_route_chunks(
                    session=session,
                    tenant_id=tenant_id,
                    study_space=study_space,
                    embedding_provider=embedding_provider,
                )
                if not chunks:
                    chunks = await load_route_source_chunks(
                        session=session,
                        tenant_id=tenant_id,
                        study_space_id=study_space_id,
                    )
            else:
                chunks = await load_route_source_chunks(
                    session=session,
                    tenant_id=tenant_id,
                    study_space_id=study_space_id,
                )
            version = await next_route_version(session=session, study_space_id=study_space_id)
            route, chapters = await persist_generated_route(
                session=session,
                study_space=study_space,
                version=version,
                chunks=chunks,
                generator=generator,
                max_chapters=max_chapters,
            )
            await session.commit()
            return route, chapters
        except IntegrityError as exc:
            await session.rollback()
            last_error = exc
    raise ValueError("Route version conflict; retry route generation") from last_error


async def list_routes_for_space(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> list[tuple[LearningRoute, list[Chapter]]]:
    await ensure_study_space_in_tenant(
        session=session,
        study_space_id=study_space_id,
        tenant_id=tenant_id,
    )
    route_rows = await session.scalars(
        select(LearningRoute)
        .where(
            LearningRoute.tenant_id == tenant_id,
            LearningRoute.study_space_id == study_space_id,
        )
        .order_by(LearningRoute.created_at.desc(), LearningRoute.version.desc())
    )
    routes = list(route_rows)
    if not routes:
        return []

    chapter_rows = await session.scalars(
        select(Chapter)
        .where(Chapter.learning_route_id.in_([route.id for route in routes]))
        .order_by(Chapter.order_index)
    )
    chapters_by_route: dict[uuid.UUID, list[Chapter]] = {route.id: [] for route in routes}
    for chapter in chapter_rows:
        chapters_by_route.setdefault(chapter.learning_route_id, []).append(chapter)
    return [(route, chapters_by_route.get(route.id, [])) for route in routes]


async def list_active_chapters(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> list[Chapter]:
    await ensure_study_space_in_tenant(
        session=session,
        study_space_id=study_space_id,
        tenant_id=tenant_id,
    )
    active_route = await session.scalar(
        select(LearningRoute).where(
            LearningRoute.tenant_id == tenant_id,
            LearningRoute.study_space_id == study_space_id,
            LearningRoute.status == LearningRouteStatus.active,
        )
    )
    if active_route is None:
        return []
    rows = await session.scalars(
        select(Chapter)
        .where(Chapter.learning_route_id == active_route.id)
        .order_by(Chapter.order_index)
    )
    return list(rows)


async def activate_route(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    route_id: uuid.UUID,
) -> tuple[LearningRoute, list[Chapter]]:
    route = await session.scalar(
        select(LearningRoute).where(
            LearningRoute.id == route_id,
            LearningRoute.tenant_id == tenant_id,
        )
    )
    if route is None:
        raise ValueError("Route not found for tenant")
    if route.status == LearningRouteStatus.archived:
        raise ValueError("Archived routes cannot be activated")

    active_routes = await session.scalars(
        select(LearningRoute).where(
            LearningRoute.tenant_id == tenant_id,
            LearningRoute.study_space_id == route.study_space_id,
            LearningRoute.status == LearningRouteStatus.active,
        )
    )
    for active_route in active_routes:
        if active_route.id != route.id:
            active_route.status = LearningRouteStatus.archived
    await session.flush()

    route.status = LearningRouteStatus.active
    route.activated_at = datetime.now(UTC)

    chapter_rows = await session.scalars(
        select(Chapter)
        .where(Chapter.learning_route_id == route.id)
        .order_by(Chapter.order_index)
    )
    chapters = list(chapter_rows)
    for index, chapter in enumerate(chapters):
        if chapter.status != ChapterStatus.completed:
            chapter.status = ChapterStatus.active if index == 0 else ChapterStatus.not_started

    study_space = await session.scalar(
        select(StudySpace).where(
            StudySpace.id == route.study_space_id,
            StudySpace.tenant_id == tenant_id,
        )
    )
    if study_space is not None:
        study_space.route_outline = build_route_outline(chapters)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("Active route conflict; retry activation") from exc
    return route, chapters


def build_route_outline(chapters: list[Chapter]) -> list[dict]:
    return [
        {
            "order": chapter.order_index,
            "title": chapter.title,
            "description": chapter.summary,
            "estimated_days": chapter.estimated_days,
        }
        for chapter in chapters
    ]
