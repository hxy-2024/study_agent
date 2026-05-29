import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRun,
    PlannerAction,
    PlannerActionStatus,
    SpacePlannerState,
    StudySpace,
)
from app.domain.dashboard.schemas import (
    DashboardAction,
    DashboardAgentRun,
    DashboardResponse,
    DashboardSpace,
)


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _supervision_refresh_count(states: list[SpacePlannerState]) -> int:
    count = 0
    for state in states:
        evidence = state.evidence or []
        count += sum(1 for item in evidence if isinstance(item, dict) and item.get("needs_supervision_refresh") is True)
    return count


def _agent_run_summary(run: AgentRun) -> str:
    output_payload = run.output_payload if isinstance(run.output_payload, dict) else {}
    summary = output_payload.get("summary")
    if isinstance(summary, str) and summary:
        return summary
    if run.error_message:
        return f"Run failed: {run.error_message}"
    return f"{_enum_value(run.agent_type)} run {_enum_value(run.status)}."


async def get_dashboard_summary(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> DashboardResponse:
    space_rows = await session.scalars(
        select(StudySpace)
        .where(
            StudySpace.tenant_id == tenant_id,
            StudySpace.owner_user_id == user_id,
        )
        .order_by(StudySpace.created_at.desc(), StudySpace.id)
    )
    spaces = list(space_rows)

    action_rows = await session.scalars(
        select(PlannerAction)
        .where(
            PlannerAction.tenant_id == tenant_id,
            PlannerAction.user_id == user_id,
            PlannerAction.status.in_([PlannerActionStatus.proposed, PlannerActionStatus.accepted]),
        )
        .order_by(PlannerAction.created_at.desc(), PlannerAction.id)
        .limit(8)
    )
    actions = list(action_rows)

    planner_state_rows = await session.scalars(
        select(SpacePlannerState).where(
            SpacePlannerState.tenant_id == tenant_id,
            SpacePlannerState.user_id == user_id,
        )
    )
    planner_states = list(planner_state_rows)

    run_rows = await session.scalars(
        select(AgentRun)
        .where(AgentRun.tenant_id == tenant_id)
        .order_by(AgentRun.created_at.desc(), AgentRun.id)
        .limit(5)
    )
    agent_runs = list(run_rows)

    return DashboardResponse(
        spaces=[
            DashboardSpace(
                id=space.id,
                name=space.name,
                goal=space.goal,
                status=_enum_value(space.status),
                target_days=space.target_days,
            )
            for space in spaces
        ],
        pending_actions=[
            DashboardAction(
                id=action.id,
                study_space_id=action.study_space_id,
                chapter_id=action.chapter_id,
                title=action.title,
                status=_enum_value(action.status),
            )
            for action in actions
        ],
        supervision_refresh_count=_supervision_refresh_count(planner_states),
        recent_agent_runs=[
            DashboardAgentRun(
                id=run.id,
                agent_type=_enum_value(run.agent_type),
                status=_enum_value(run.status),
                summary=_agent_run_summary(run),
            )
            for run in agent_runs
        ],
    )
