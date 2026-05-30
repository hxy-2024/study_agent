import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.study_spaces.export import export_study_space, format_study_space_markdown
from app.domain.study_spaces.schemas import StudySpaceCreate, StudySpaceRead
from app.domain.study_spaces.service import (
    archive_study_space,
    create_study_space,
    list_archived_study_spaces,
    list_study_spaces,
    restore_study_space,
)

router = APIRouter(prefix="/study-spaces", tags=["study-spaces"])


@router.get("", response_model=list[StudySpaceRead])
async def list_spaces(
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> list:
    return await list_study_spaces(session=session, tenant_id=context.tenant_id)


@router.get("/archived", response_model=list[StudySpaceRead])
async def list_archived_spaces(
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> list:
    return await list_archived_study_spaces(session=session, tenant_id=context.tenant_id)


@router.post("", response_model=StudySpaceRead, status_code=201)
async def create_space(
    payload: StudySpaceCreate,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
):
    return await create_study_space(
        session=session,
        payload=payload,
        tenant_id=context.tenant_id,
        owner_user_id=context.user_id,
    )


@router.delete("/{study_space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await archive_study_space(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{study_space_id}/restore", response_model=StudySpaceRead)
async def restore_space(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await restore_study_space(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{study_space_id}/export")
async def export_space(
    study_space_id: uuid.UUID,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        payload = await export_study_space(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if format == "markdown":
        return PlainTextResponse(
            format_study_space_markdown(payload),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{study_space_id}.md"'},
        )
    return payload
