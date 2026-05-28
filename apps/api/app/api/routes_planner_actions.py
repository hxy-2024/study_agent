import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.planner_actions.schemas import (
    CreatePlannerActionsRequest,
    PlannerActionListResponse,
    PlannerActionResponse,
    UpdatePlannerActionStatusRequest,
)
from app.domain.planner_actions.service import (
    create_actions_from_latest_planner_state,
    list_planner_actions,
    update_planner_action_status,
)

router = APIRouter(tags=["planner-actions"])


def map_planner_action_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 404 if "not found" in message.lower() else 400
    return HTTPException(status_code=status_code, detail=message)


@router.get("/study-spaces/{study_space_id}/planner-actions", response_model=PlannerActionListResponse)
async def read_planner_actions(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> PlannerActionListResponse:
    try:
        return await list_planner_actions(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise map_planner_action_error(exc) from exc


@router.post("/planner-actions/from-latest-state", response_model=PlannerActionListResponse, status_code=201)
async def create_planner_actions(
    payload: CreatePlannerActionsRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> PlannerActionListResponse:
    try:
        return await create_actions_from_latest_planner_state(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            study_space_id=payload.study_space_id,
        )
    except ValueError as exc:
        raise map_planner_action_error(exc) from exc


@router.post("/planner-actions/{action_id}/status", response_model=PlannerActionResponse)
async def update_action_status(
    action_id: uuid.UUID,
    payload: UpdatePlannerActionStatusRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> PlannerActionResponse:
    try:
        return await update_planner_action_status(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            action_id=action_id,
            status=payload.status,
        )
    except ValueError as exc:
        raise map_planner_action_error(exc) from exc
