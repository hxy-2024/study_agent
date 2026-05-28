import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.agent_runtime.schemas import AgentRunTimelineResponse
from app.domain.agent_runtime.service import (
    list_agent_runs_for_chapter,
    list_agent_runs_for_session,
    list_agent_runs_for_study_space,
)

router = APIRouter(tags=["agent-runtime"])


def map_agent_runtime_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/study-spaces/{study_space_id}/agent-runs",
    response_model=AgentRunTimelineResponse,
)
async def read_study_space_agent_runs(
    study_space_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> AgentRunTimelineResponse:
    try:
        return await list_agent_runs_for_study_space(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
            limit=limit,
        )
    except ValueError as exc:
        raise map_agent_runtime_error(exc) from exc


@router.get(
    "/chapters/{chapter_id}/agent-runs",
    response_model=AgentRunTimelineResponse,
)
async def read_chapter_agent_runs(
    chapter_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> AgentRunTimelineResponse:
    try:
        return await list_agent_runs_for_chapter(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=chapter_id,
            limit=limit,
        )
    except ValueError as exc:
        raise map_agent_runtime_error(exc) from exc


@router.get(
    "/sessions/{session_id}/agent-runs",
    response_model=AgentRunTimelineResponse,
)
async def read_session_agent_runs(
    session_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> AgentRunTimelineResponse:
    try:
        return await list_agent_runs_for_session(
            session=session,
            tenant_id=context.tenant_id,
            session_id=session_id,
            limit=limit,
        )
    except ValueError as exc:
        raise map_agent_runtime_error(exc) from exc
