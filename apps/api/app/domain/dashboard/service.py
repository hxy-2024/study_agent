import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRun,
    AgentRunStatus,
    AgentType,
    Chapter,
    MasteryRecord,
    PlannerAction,
    PlannerActionStatus,
    Quiz,
    QuizSubmission,
    SpacePlannerState,
    StudySpace,
    StudySpaceStatus,
)
from app.domain.dashboard.recommendations import STRATEGY_VERSION
from app.domain.dashboard.recommendations import build_main_agent_recommendation
from app.domain.dashboard.schemas import (
    DashboardAction,
    DashboardAgentRun,
    DashboardRecommendation,
    DashboardRecommendationRequest,
    DashboardResponse,
    DashboardSpace,
)
from app.domain.review_planner.schemas import ReviewCandidate
from app.domain.review_planner.service import build_review_candidates
from app.domain.quiz_mastery.schemas import QuizMasterySignal
from app.domain.quiz_mastery.service import build_quiz_mastery_signals
from app.domain.learning_signals.service import (
    learning_signal_from_quiz_mastery,
    learning_signal_from_review_candidate,
    upsert_learning_signal_drafts,
)
from app.domain.review_queue.service import build_review_queue, get_review_queue
from app.domain.review_queue.schemas import ReviewQueueItem


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
    active_space_ids = select(StudySpace.id).where(
        StudySpace.tenant_id == tenant_id,
        StudySpace.owner_user_id == user_id,
        StudySpace.status != StudySpaceStatus.archived,
    )
    space_rows = await session.scalars(
        select(StudySpace)
        .where(
            StudySpace.tenant_id == tenant_id,
            StudySpace.owner_user_id == user_id,
            StudySpace.status != StudySpaceStatus.archived,
        )
        .order_by(StudySpace.created_at.desc(), StudySpace.id)
    )
    spaces = list(space_rows)

    action_rows = await session.scalars(
        select(PlannerAction)
        .where(
            PlannerAction.tenant_id == tenant_id,
            PlannerAction.user_id == user_id,
            PlannerAction.study_space_id.in_(active_space_ids),
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
            SpacePlannerState.study_space_id.in_(active_space_ids),
        )
    )
    planner_states = list(planner_state_rows)

    run_rows = await session.scalars(
        select(AgentRun)
        .where(
            AgentRun.tenant_id == tenant_id,
            AgentRun.study_space_id.in_(active_space_ids),
        )
        .order_by(AgentRun.created_at.desc(), AgentRun.id)
        .limit(5)
    )
    agent_runs = list(run_rows)

    chapter_rows = await session.scalars(
        select(Chapter)
        .where(
            Chapter.tenant_id == tenant_id,
            Chapter.study_space_id.in_(active_space_ids),
        )
        .order_by(Chapter.study_space_id, Chapter.order_index, Chapter.id)
    )
    chapters = list(chapter_rows)

    mastery_rows = await session.scalars(
        select(MasteryRecord).where(
            MasteryRecord.tenant_id == tenant_id,
            MasteryRecord.user_id == user_id,
            MasteryRecord.study_space_id.in_(active_space_ids),
        )
    )
    mastery_records = list(mastery_rows)

    quiz_rows = await session.scalars(
        select(Quiz).where(
            Quiz.tenant_id == tenant_id,
            Quiz.user_id == user_id,
            Quiz.study_space_id.in_(active_space_ids),
        )
    )
    quizzes = list(quiz_rows)
    submission_rows = await session.scalars(
        select(QuizSubmission).where(
            QuizSubmission.tenant_id == tenant_id,
            QuizSubmission.user_id == user_id,
            QuizSubmission.chapter_id.in_(select(Chapter.id).where(Chapter.study_space_id.in_(active_space_ids))),
        )
    )
    quiz_submissions = list(submission_rows)

    review_candidates = build_review_candidates(chapters=chapters, mastery_records=mastery_records)
    quiz_mastery_signals = build_quiz_mastery_signals(
        chapters=chapters,
        mastery_records=mastery_records,
        submissions=quiz_submissions,
    )
    review_queue = build_review_queue(
        chapters=chapters,
        review_candidates=review_candidates,
        quiz_mastery_signals=quiz_mastery_signals,
        quizzes=quizzes,
        planner_actions=actions,
    )

    today_recommendation = await get_main_agent_recommendation(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        request=DashboardRecommendationRequest(),
        spaces=spaces,
        chapters=chapters,
        planner_actions=actions,
        mastery_records=mastery_records,
        quizzes=quizzes,
        review_candidates=review_candidates,
        quiz_mastery_signals=quiz_mastery_signals,
        review_queue=review_queue,
        persist_run=False,
    )

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
        today_recommendation=today_recommendation,
        review_queue=review_queue,
    )


async def _load_recommendation_signals(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[list[StudySpace], list[Chapter], list[PlannerAction], list[MasteryRecord], list[Quiz], list[QuizSubmission]]:
    active_space_ids = select(StudySpace.id).where(
        StudySpace.tenant_id == tenant_id,
        StudySpace.owner_user_id == user_id,
        StudySpace.status != StudySpaceStatus.archived,
    )
    space_rows = await session.scalars(
        select(StudySpace)
        .where(
            StudySpace.tenant_id == tenant_id,
            StudySpace.owner_user_id == user_id,
            StudySpace.status != StudySpaceStatus.archived,
        )
        .order_by(StudySpace.created_at.desc(), StudySpace.id)
    )
    spaces = list(space_rows)
    chapter_rows = await session.scalars(
        select(Chapter)
        .where(
            Chapter.tenant_id == tenant_id,
            Chapter.study_space_id.in_(active_space_ids),
        )
        .order_by(Chapter.study_space_id, Chapter.order_index, Chapter.id)
    )
    chapters = list(chapter_rows)
    action_rows = await session.scalars(
        select(PlannerAction)
        .where(
            PlannerAction.tenant_id == tenant_id,
            PlannerAction.user_id == user_id,
            PlannerAction.study_space_id.in_(active_space_ids),
            PlannerAction.status.in_([PlannerActionStatus.proposed, PlannerActionStatus.accepted]),
        )
        .order_by(PlannerAction.created_at.desc(), PlannerAction.id)
        .limit(8)
    )
    planner_actions = list(action_rows)
    mastery_rows = await session.scalars(
        select(MasteryRecord).where(
            MasteryRecord.tenant_id == tenant_id,
            MasteryRecord.user_id == user_id,
            MasteryRecord.study_space_id.in_(active_space_ids),
        )
    )
    mastery_records = list(mastery_rows)
    quiz_rows = await session.scalars(
        select(Quiz).where(
            Quiz.tenant_id == tenant_id,
            Quiz.user_id == user_id,
            Quiz.study_space_id.in_(active_space_ids),
        )
    )
    quizzes = list(quiz_rows)
    submission_rows = await session.scalars(
        select(QuizSubmission).where(
            QuizSubmission.tenant_id == tenant_id,
            QuizSubmission.user_id == user_id,
            QuizSubmission.chapter_id.in_(select(Chapter.id).where(Chapter.study_space_id.in_(active_space_ids))),
        )
    )
    quiz_submissions = list(submission_rows)
    return spaces, chapters, planner_actions, mastery_records, quizzes, quiz_submissions


async def get_main_agent_recommendation(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    request: DashboardRecommendationRequest,
    spaces: list[StudySpace] | None = None,
    chapters: list[Chapter] | None = None,
    planner_actions: list[PlannerAction] | None = None,
    mastery_records: list[MasteryRecord] | None = None,
    quizzes: list[Quiz] | None = None,
    review_candidates: list[ReviewCandidate] | None = None,
    quiz_mastery_signals: list[QuizMasterySignal] | None = None,
    review_queue: list[ReviewQueueItem] | None = None,
    persist_run: bool = True,
) -> DashboardRecommendation:
    quiz_submissions: list[QuizSubmission] = []
    if spaces is None or chapters is None or planner_actions is None or mastery_records is None or quizzes is None:
        spaces, chapters, planner_actions, mastery_records, quizzes, quiz_submissions = await _load_recommendation_signals(
            session=session,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    if review_candidates is None:
        review_candidates = build_review_candidates(chapters=chapters, mastery_records=mastery_records)
    if quiz_mastery_signals is None:
        quiz_mastery_signals = build_quiz_mastery_signals(
            chapters=chapters,
            mastery_records=mastery_records,
            submissions=quiz_submissions,
        )
    if persist_run and hasattr(session, "scalar"):
        drafts = [
            learning_signal_from_review_candidate(
                candidate=candidate,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            for candidate in review_candidates
        ] + [
            learning_signal_from_quiz_mastery(
                signal=signal,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            for signal in quiz_mastery_signals
            if signal.retake_recommended
        ]
        if drafts:
            await upsert_learning_signal_drafts(session=session, drafts=drafts)
            review_queue = await get_review_queue(
                session=session,
                tenant_id=tenant_id,
                user_id=user_id,
            )
    if review_queue is None:
        review_queue = build_review_queue(
            chapters=chapters,
            review_candidates=review_candidates,
            quiz_mastery_signals=quiz_mastery_signals,
            quizzes=quizzes,
            planner_actions=planner_actions,
        )

    recommendation = build_main_agent_recommendation(
        spaces=spaces,
        chapters=chapters,
        planner_actions=planner_actions,
        mastery_records=mastery_records,
        quizzes=quizzes,
        review_candidates=review_candidates,
        quiz_mastery_signals=quiz_mastery_signals,
        review_queue=review_queue,
        request=request,
    )
    if recommendation is None:
        recommendation = DashboardRecommendation(
            title="Create your first study space",
            action_label="Create space",
            action_url="/spaces/new",
            recommendation_type="create_space",
            reason="No active learning space exists yet.",
            estimated_minutes=10,
        )

    if recommendation.study_space_id is None or not persist_run:
        return recommendation

    run = AgentRun(
        tenant_id=tenant_id,
        study_space_id=recommendation.study_space_id,
        agent_type=AgentType.main_agent,
        status=AgentRunStatus.completed,
        model="deterministic",
        input_payload={
            "request": request.model_dump(),
            "signal_counts": recommendation.source_signals,
            "strategy_version": STRATEGY_VERSION,
            "selected_queue_item": review_queue[0].model_dump(mode="json") if review_queue else None,
        },
        output_payload=recommendation.model_dump(mode="json"),
    )
    try:
        session.add(run)
        await session.commit()
    except Exception:
        rollback = getattr(session, "rollback", None)
        if rollback is not None:
            await rollback()
        return recommendation

    recommendation.agent_run_id = run.id
    return recommendation
