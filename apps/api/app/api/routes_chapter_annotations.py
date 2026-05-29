import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.chapter_annotations.schemas import (
    ChapterAnnotationCreateRequest,
    ChapterAnnotationListResponse,
    ChapterAnnotationMutationResponse,
    ChapterAnnotationUpdateRequest,
)
from app.domain.chapter_annotations.service import (
    create_chapter_annotation,
    delete_chapter_annotation,
    list_chapter_annotations,
    update_chapter_annotation,
)

router = APIRouter(tags=["chapter-annotations"])


def map_annotation_error(exc: ValueError) -> HTTPException:
    status_code = 404 if "not found" in str(exc).lower() else 400
    return HTTPException(status_code=status_code, detail=str(exc))


@router.get("/chapters/{chapter_id}/annotations", response_model=ChapterAnnotationListResponse)
async def read_chapter_annotations(
    chapter_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: CurrentUserContext = Depends(get_authorized_user_context),
) -> ChapterAnnotationListResponse:
    try:
        annotations = await list_chapter_annotations(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=chapter_id,
        )
    except ValueError as exc:
        raise map_annotation_error(exc) from exc
    return ChapterAnnotationListResponse(annotations=annotations)


@router.post("/chapters/{chapter_id}/annotations", response_model=ChapterAnnotationMutationResponse)
async def create_annotation(
    chapter_id: uuid.UUID,
    payload: ChapterAnnotationCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    context: CurrentUserContext = Depends(get_authorized_user_context),
) -> ChapterAnnotationMutationResponse:
    try:
        annotation = await create_chapter_annotation(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            chapter_id=chapter_id,
            payload=payload,
        )
    except ValueError as exc:
        raise map_annotation_error(exc) from exc
    return ChapterAnnotationMutationResponse(annotation=annotation)


@router.patch("/chapter-annotations/{annotation_id}", response_model=ChapterAnnotationMutationResponse)
async def update_annotation(
    annotation_id: uuid.UUID,
    payload: ChapterAnnotationUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    context: CurrentUserContext = Depends(get_authorized_user_context),
) -> ChapterAnnotationMutationResponse:
    try:
        annotation = await update_chapter_annotation(
            session=session,
            tenant_id=context.tenant_id,
            annotation_id=annotation_id,
            payload=payload,
        )
    except ValueError as exc:
        raise map_annotation_error(exc) from exc
    return ChapterAnnotationMutationResponse(annotation=annotation)


@router.delete("/chapter-annotations/{annotation_id}", status_code=204)
async def delete_annotation(
    annotation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: CurrentUserContext = Depends(get_authorized_user_context),
) -> Response:
    try:
        await delete_chapter_annotation(
            session=session,
            tenant_id=context.tenant_id,
            annotation_id=annotation_id,
        )
    except ValueError as exc:
        raise map_annotation_error(exc) from exc
    return Response(status_code=204)
