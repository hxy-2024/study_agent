import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlannerAction, PlannerActionStatus, PlannerActionType, SpacePlannerState, StudySpace
from app.domain.planner_actions.schemas import PlannerActionListResponse, PlannerActionResponse


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def planner_action_response(action: PlannerAction) -> PlannerActionResponse:
    return PlannerActionResponse(
        id=action.id,
        study_space_id=action.study_space_id,
        chapter_id=action.chapter_id,
        source_planner_state_id=action.source_planner_state_id,
        action_type=_enum_value(action.action_type),
        status=_enum_value(action.status),
        title=action.title,
        rationale=action.rationale,
        payload=action.payload or {},
        created_at=action.created_at,
        updated_at=action.updated_at,
    )


def build_actions_from_planner_state(state: SpacePlannerState) -> list[PlannerAction]:
    actions: list[PlannerAction] = []
    for review in state.review_recommendations or []:
        actions.append(
            PlannerAction(
                id=uuid.uuid4(),
                tenant_id=state.tenant_id,
                user_id=state.user_id,
                study_space_id=state.study_space_id,
                chapter_id=uuid.UUID(str(review["chapter_id"])),
                source_planner_state_id=state.id,
                action_type=PlannerActionType.review_chapter,
                status=PlannerActionStatus.proposed,
                title=review["action"],
                rationale=f'{review["title"]}: {review["reason"]}',
                payload=review,
            )
        )
    for proposal in state.route_adjustments or []:
        chapter_id = proposal.get("chapter_id")
        actions.append(
            PlannerAction(
                id=uuid.uuid4(),
                tenant_id=state.tenant_id,
                user_id=state.user_id,
                study_space_id=state.study_space_id,
                chapter_id=uuid.UUID(str(chapter_id)) if chapter_id else None,
                source_planner_state_id=state.id,
                action_type=PlannerActionType.route_adjustment,
                status=PlannerActionStatus.proposed,
                title=proposal["title"],
                rationale=proposal["rationale"],
                payload=proposal,
            )
        )
    return actions


async def ensure_study_space_for_actions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> StudySpace:
    study_space = await session.scalar(
        select(StudySpace).where(
            StudySpace.id == study_space_id,
            StudySpace.tenant_id == tenant_id,
            StudySpace.owner_user_id == user_id,
        )
    )
    if study_space is None:
        raise ValueError("Study space not found for user")
    return study_space


async def list_planner_actions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> PlannerActionListResponse:
    await ensure_study_space_for_actions(session, tenant_id, user_id, study_space_id)
    rows = await session.scalars(
        select(PlannerAction)
        .where(
            PlannerAction.tenant_id == tenant_id,
            PlannerAction.user_id == user_id,
            PlannerAction.study_space_id == study_space_id,
        )
        .order_by(PlannerAction.created_at.desc(), PlannerAction.id)
    )
    return PlannerActionListResponse(actions=[planner_action_response(action) for action in rows])


async def create_actions_from_latest_planner_state(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> PlannerActionListResponse:
    await ensure_study_space_for_actions(session, tenant_id, user_id, study_space_id)
    state = await session.scalar(
        select(SpacePlannerState)
        .where(
            SpacePlannerState.tenant_id == tenant_id,
            SpacePlannerState.user_id == user_id,
            SpacePlannerState.study_space_id == study_space_id,
        )
        .order_by(SpacePlannerState.updated_at.desc(), SpacePlannerState.id)
    )
    if state is None:
        raise ValueError("Space planner state not found")

    actions = build_actions_from_planner_state(state)
    for action in actions:
        session.add(action)
    await session.commit()
    return PlannerActionListResponse(actions=[planner_action_response(action) for action in actions])


async def update_planner_action_status(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    action_id: uuid.UUID,
    status: str,
) -> PlannerActionResponse:
    try:
        next_status = PlannerActionStatus(status)
    except ValueError as exc:
        raise ValueError("Unsupported planner action status") from exc

    action = await session.scalar(
        select(PlannerAction).where(
            PlannerAction.id == action_id,
            PlannerAction.tenant_id == tenant_id,
            PlannerAction.user_id == user_id,
        )
    )
    if action is None:
        raise ValueError("Planner action not found")
    if action.status == PlannerActionStatus.dismissed:
        raise ValueError("Cannot update dismissed planner action")
    if action.status == PlannerActionStatus.completed and next_status != PlannerActionStatus.completed:
        raise ValueError("Cannot reopen completed planner action")

    action.status = next_status
    action.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(action)
    return planner_action_response(action)
