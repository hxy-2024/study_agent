import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.space_planner.schemas import RunSpacePlannerRequest, SpacePlannerStateResponse
from app.domain.space_planner.service import (
    build_space_planner_state_response,
    generate_space_planner_state,
    get_space_planner_state,
)

router = APIRouter(tags=["space-planner"])


def map_space_planner_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 404 if "not found" in message.lower() else 400
    return HTTPException(status_code=status_code, detail=message)


@router.get("/study-spaces/{study_space_id}/planner-state", response_model=SpacePlannerStateResponse)
async def read_space_planner_state(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> SpacePlannerStateResponse:
    try:
        state = await get_space_planner_state(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise map_space_planner_error(exc) from exc
    if state is None:
        raise HTTPException(status_code=404, detail="Space planner state not found")
    return build_space_planner_state_response(state)


@router.post("/agents/space-planner/run", response_model=SpacePlannerStateResponse)
async def run_space_planner(
    payload: RunSpacePlannerRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> SpacePlannerStateResponse:
    try:
        return await generate_space_planner_state(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            study_space_id=payload.study_space_id,
        )
    except ValueError as exc:
        raise map_space_planner_error(exc) from exc
