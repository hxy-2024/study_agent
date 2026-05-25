import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.domain.study_spaces.schemas import StudySpaceCreate, StudySpaceRead
from app.domain.study_spaces.service import create_study_space, list_study_spaces

router = APIRouter(prefix="/study-spaces", tags=["study-spaces"])


@router.get("", response_model=list[StudySpaceRead])
async def list_spaces(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list:
    return await list_study_spaces(session, tenant_id)


@router.post("", response_model=StudySpaceRead, status_code=201)
async def create_space(
    payload: StudySpaceCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await create_study_space(session, payload)
