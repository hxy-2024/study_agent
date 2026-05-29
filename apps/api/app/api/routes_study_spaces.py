import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.study_spaces.schemas import StudySpaceCreate, StudySpaceRead
from app.domain.study_spaces.service import archive_study_space, create_study_space, list_study_spaces

router = APIRouter(prefix="/study-spaces", tags=["study-spaces"])


@router.get("", response_model=list[StudySpaceRead])
async def list_spaces(
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> list:
    return await list_study_spaces(session=session, tenant_id=context.tenant_id)


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
