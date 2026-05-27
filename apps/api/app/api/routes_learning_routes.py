import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.learning_routes.generator import DeterministicRouteGenerator
from app.domain.learning_routes.schemas import (
    ChapterResponse,
    ChaptersListResponse,
    LearningRouteResponse,
    RouteDraftRequest,
    RoutesListResponse,
    RouteWithChaptersResponse,
)
from app.domain.learning_routes.service import (
    activate_route,
    create_route_draft,
    list_active_chapters,
    list_routes_for_space,
)

router = APIRouter(tags=["learning-routes"])


def route_response(route) -> LearningRouteResponse:
    return LearningRouteResponse(
        id=route.id,
        study_space_id=route.study_space_id,
        version=route.version,
        status=route.status.value,
        title=route.title,
        summary=route.summary,
        generation_strategy=route.generation_strategy,
        created_at=route.created_at,
        activated_at=route.activated_at,
    )


def chapter_response(chapter) -> ChapterResponse:
    return ChapterResponse(
        id=chapter.id,
        learning_route_id=chapter.learning_route_id,
        order_index=chapter.order_index,
        title=chapter.title,
        goal=chapter.goal,
        summary=chapter.summary,
        estimated_days=chapter.estimated_days,
        status=chapter.status.value,
        source_chunk_refs=chapter.source_chunk_refs,
    )


@router.post(
    "/study-spaces/{study_space_id}/route-drafts",
    response_model=RouteWithChaptersResponse,
    status_code=201,
)
async def create_study_space_route_draft(
    study_space_id: uuid.UUID,
    payload: RouteDraftRequest | None = None,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> RouteWithChaptersResponse:
    request = payload or RouteDraftRequest()
    try:
        route, chapters = await create_route_draft(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
            generator=DeterministicRouteGenerator(),
            max_chapters=request.max_chapters,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return RouteWithChaptersResponse(
        route=route_response(route),
        chapters=[chapter_response(chapter) for chapter in chapters],
    )


@router.get("/study-spaces/{study_space_id}/routes", response_model=RoutesListResponse)
async def get_study_space_routes(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> RoutesListResponse:
    try:
        routes = await list_routes_for_space(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RoutesListResponse(
        routes=[
            RouteWithChaptersResponse(
                route=route_response(route),
                chapters=[chapter_response(chapter) for chapter in chapters],
            )
            for route, chapters in routes
        ]
    )


@router.get("/study-spaces/{study_space_id}/chapters", response_model=ChaptersListResponse)
async def get_active_chapters(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChaptersListResponse:
    try:
        chapters = await list_active_chapters(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChaptersListResponse(chapters=[chapter_response(chapter) for chapter in chapters])


@router.post("/routes/{route_id}/activate", response_model=RouteWithChaptersResponse)
async def activate_learning_route(
    route_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> RouteWithChaptersResponse:
    try:
        route, chapters = await activate_route(
            session=session,
            tenant_id=context.tenant_id,
            route_id=route_id,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Route not found for tenant" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return RouteWithChaptersResponse(
        route=route_response(route),
        chapters=[chapter_response(chapter) for chapter in chapters],
    )
