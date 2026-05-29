import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRun,
    AgentRunStatus,
    AgentType,
    Chapter,
    PlannerAction,
    PlannerActionStatus,
    PlannerActionType,
    Session,
    SessionStatus,
    SpacePlannerState,
    StudySpace,
)
from app.domain.planner_actions.schemas import (
    PlannerActionExecutionResponse,
    PlannerActionListResponse,
    PlannerActionResponse,
)
from app.domain.sessions.service import build_session_response


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


def _runtime_signal_types(output_payload: dict | None) -> list[str]:
    signal_types: list[str] = []
    if not isinstance(output_payload, dict):
        return signal_types

    for signal in output_payload.get("learning_signals") or []:
        if not isinstance(signal, dict):
            continue
        signal_type = signal.get("type")
        signal_value = signal.get("value")
        if not isinstance(signal_type, str):
            continue
        if signal_value is True:
            signal_types.append(signal_type)
        elif signal_type == "evidence_used" and signal_value is False:
            signal_types.append("evidence_missing")
    return signal_types


def _runtime_action_kind(signal_types: list[str]) -> str | None:
    if "confusion_detected" in signal_types:
        return "review_confusion"
    if "needs_review" in signal_types:
        return "review_chapter"
    if "evidence_missing" in signal_types:
        return "strengthen_evidence"
    return None


def _runtime_action_title(kind: str, chapter_title: str) -> str:
    if kind == "review_confusion":
        return f"Review confusion in {chapter_title}"
    if kind == "strengthen_evidence":
        return f"Strengthen evidence for {chapter_title}"
    return f"Review {chapter_title}"


def _runtime_action_rationale(signal_types: list[str]) -> str:
    if "confusion_detected" in signal_types:
        return "The session tutor detected learner confusion in recent completed session signals."
    if "needs_review" in signal_types:
        return "Recent completed session signals indicate this chapter needs review."
    if "evidence_missing" in signal_types:
        return "Recent completed session signals indicate the answer was not grounded in retrieved evidence."
    return "Recent completed session signals indicate follow-up review is needed."


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


async def _ensure_chapter_for_runtime_actions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> Chapter:
    chapter = await session.scalar(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.tenant_id == tenant_id,
            Chapter.study_space_id == study_space_id,
        )
    )
    if chapter is None:
        raise ValueError("Chapter not found for study space")
    return chapter


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


def _has_runtime_duplicate(
    existing_actions: list[PlannerAction],
    *,
    chapter_id: uuid.UUID,
    agent_run_id: uuid.UUID,
    action_kind: str,
) -> bool:
    for action in existing_actions:
        payload = action.payload or {}
        if (
            action.chapter_id == chapter_id
            and payload.get("source") == "runtime_signal"
            and payload.get("agent_run_id") == str(agent_run_id)
            and payload.get("action_kind") == action_kind
        ):
            return True
    return False


def _planner_action_from_row(row: Any) -> PlannerAction:
    return row if isinstance(row, PlannerAction) else row[0]


async def create_actions_from_runtime_signals(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    study_space_id: uuid.UUID,
    chapter_id: uuid.UUID | None = None,
) -> PlannerActionListResponse:
    await ensure_study_space_for_actions(session, tenant_id, user_id, study_space_id)
    if chapter_id is not None:
        await _ensure_chapter_for_runtime_actions(session, tenant_id, study_space_id, chapter_id)

    runs_statement = (
        select(AgentRun, Session, Chapter)
        .join(Session, AgentRun.session_id == Session.id)
        .join(Chapter, Session.chapter_id == Chapter.id)
        .where(
            AgentRun.tenant_id == tenant_id,
            AgentRun.study_space_id == study_space_id,
            AgentRun.agent_type == AgentType.session_tutor,
            AgentRun.status == AgentRunStatus.completed,
            Session.tenant_id == tenant_id,
            Session.study_space_id == study_space_id,
            Chapter.tenant_id == tenant_id,
            Chapter.study_space_id == study_space_id,
        )
        .order_by(AgentRun.completed_at.desc().nulls_last(), AgentRun.created_at.desc(), AgentRun.id)
    )
    if chapter_id is not None:
        runs_statement = runs_statement.where(Chapter.id == chapter_id)

    run_rows = (await session.execute(runs_statement)).all()
    existing_statement = select(PlannerAction).where(
        PlannerAction.tenant_id == tenant_id,
        PlannerAction.user_id == user_id,
        PlannerAction.study_space_id == study_space_id,
        PlannerAction.action_type == PlannerActionType.review_chapter,
        PlannerAction.status.notin_([PlannerActionStatus.dismissed, PlannerActionStatus.completed]),
    )
    if chapter_id is not None:
        existing_statement = existing_statement.where(PlannerAction.chapter_id == chapter_id)
    existing_actions = [_planner_action_from_row(row) for row in (await session.execute(existing_statement)).all()]

    actions: list[PlannerAction] = []
    for agent_run, runtime_session, chapter in run_rows:
        signal_types = _runtime_signal_types(agent_run.output_payload)
        action_kind = _runtime_action_kind(signal_types)
        if action_kind is None:
            continue
        if _has_runtime_duplicate(
            existing_actions,
            chapter_id=chapter.id,
            agent_run_id=agent_run.id,
            action_kind=action_kind,
        ):
            continue

        action = PlannerAction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            study_space_id=study_space_id,
            chapter_id=chapter.id,
            action_type=PlannerActionType.review_chapter,
            status=PlannerActionStatus.proposed,
            title=_runtime_action_title(action_kind, chapter.title),
            rationale=_runtime_action_rationale(signal_types),
            payload={
                "source": "runtime_signal",
                "action_kind": action_kind,
                "agent_run_id": str(agent_run.id),
                "session_id": str(runtime_session.id),
                "signal_types": signal_types,
            },
        )
        actions.append(action)
        existing_actions.append(action)
        if len(actions) >= 5:
            break

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


def _review_session_id_from_payload(payload: dict) -> uuid.UUID | None:
    execution = payload.get("execution")
    if not isinstance(execution, dict):
        return None
    raw_session_id = execution.get("review_session_id")
    if not isinstance(raw_session_id, str):
        return None
    try:
        return uuid.UUID(raw_session_id)
    except ValueError:
        return None


async def _load_review_session(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    chapter_id: uuid.UUID,
    session_id: uuid.UUID,
) -> Session | None:
    return await session.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.tenant_id == tenant_id,
            Session.study_space_id == study_space_id,
            Session.chapter_id == chapter_id,
        )
    )


async def start_review_for_planner_action(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    action_id: uuid.UUID,
) -> PlannerActionExecutionResponse:
    action = await session.scalar(
        select(PlannerAction).where(
            PlannerAction.id == action_id,
            PlannerAction.tenant_id == tenant_id,
            PlannerAction.user_id == user_id,
        )
    )
    if action is None:
        raise ValueError("Planner action not found")
    if action.action_type != PlannerActionType.review_chapter:
        raise ValueError("Only review chapter actions can start a review session")
    if action.chapter_id is None:
        raise ValueError("Review action is missing a chapter")
    if action.status == PlannerActionStatus.dismissed:
        raise ValueError("Cannot start review for dismissed planner action")
    if action.status == PlannerActionStatus.completed:
        raise ValueError("Cannot start review for completed planner action")

    payload = dict(action.payload or {})
    existing_session_id = _review_session_id_from_payload(payload)
    review_session = None
    if existing_session_id is not None:
        review_session = await _load_review_session(
            session=session,
            tenant_id=tenant_id,
            study_space_id=action.study_space_id,
            chapter_id=action.chapter_id,
            session_id=existing_session_id,
        )

    if review_session is None:
        review_session = Session(
            tenant_id=tenant_id,
            study_space_id=action.study_space_id,
            chapter_id=action.chapter_id,
            title=f"Review: {action.title}"[:200],
            status=SessionStatus.active,
            summary=action.rationale,
        )
        session.add(review_session)
        await session.flush()

    payload["execution"] = {
        **(payload.get("execution") if isinstance(payload.get("execution"), dict) else {}),
        "review_session_id": str(review_session.id),
        "started_from_action_id": str(action.id),
    }
    action.payload = payload
    action.status = PlannerActionStatus.accepted
    action.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(action)
    await session.refresh(review_session)
    return PlannerActionExecutionResponse(
        action=planner_action_response(action),
        session=build_session_response(review_session),
    )
