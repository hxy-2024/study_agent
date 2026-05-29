import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.chapter_mentor_state.schemas import ChapterMentorStateResponse
from app.domain.chapter_mentor_state.service import (
    build_chapter_mentor_state_response,
    generate_chapter_mentor_state,
    get_chapter_mentor_state,
    get_latest_session_tutor_run_at,
)

router = APIRouter(tags=["chapter-mentor-state"])


class ChapterMentorStateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: uuid.UUID


@router.get("/chapters/{chapter_id}/mentor-state", response_model=ChapterMentorStateResponse)
async def read_chapter_mentor_state(
    chapter_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterMentorStateResponse:
    state = await get_chapter_mentor_state(
        session=session,
        tenant_id=context.tenant_id,
        chapter_id=chapter_id,
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Chapter mentor state not found")
    latest_session_tutor_run_at = await get_latest_session_tutor_run_at(
        session=session,
        tenant_id=context.tenant_id,
        chapter_id=chapter_id,
    )
    return build_chapter_mentor_state_response(
        state,
        latest_session_tutor_run_at=latest_session_tutor_run_at,
    )


@router.post("/agents/chapter-summary/run", response_model=ChapterMentorStateResponse)
async def run_chapter_summary(
    payload: ChapterMentorStateRunRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterMentorStateResponse:
    try:
        return await generate_chapter_mentor_state(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=payload.chapter_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
