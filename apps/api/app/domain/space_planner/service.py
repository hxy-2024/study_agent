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
    ChapterMentorState,
    ChapterStatus,
    LearningRoute,
    LearningRouteStatus,
    MasteryRecord,
    SpacePlannerState,
    Session,
    StudySpace,
)
from app.domain.chapter_mentor_state.service import needs_supervision_refresh
from app.domain.space_planner.schemas import (
    PlannerChapterRisk,
    PlannerReviewRecommendation,
    PlannerRouteAdjustment,
    SpacePlannerStateResponse,
)


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _chapter_status(chapter: Any) -> str:
    return _enum_value(getattr(chapter, "status", "not_started"))


def _mastery_level(record: Any) -> str:
    return _enum_value(getattr(record, "level", "new"))


def _mentor_signal_count(mentor: Any) -> int:
    evidence = getattr(mentor, "evidence", None)
    if not isinstance(evidence, list):
        return 0
    return sum(1 for item in evidence if isinstance(item, dict) and item.get("kind") == "learning_signal")


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _iso_datetime(value: Any) -> str | None:
    parsed = _as_datetime(value)
    return parsed.isoformat() if parsed else None


def build_supervision_freshness(
    chapters: list[Any],
    mentor_states: dict[uuid.UUID, Any],
    latest_tutor_runs: dict[uuid.UUID, Any],
) -> dict[uuid.UUID, dict[str, Any]]:
    freshness: dict[uuid.UUID, dict[str, Any]] = {}
    for chapter in chapters:
        mentor = mentor_states.get(chapter.id)
        mentor_updated_at = _as_datetime(getattr(mentor, "updated_at", None))
        latest_tutor_run_at = _as_datetime(latest_tutor_runs.get(chapter.id))
        freshness[chapter.id] = {
            "mentor_state_updated_at": _iso_datetime(mentor_updated_at),
            "latest_session_tutor_run_at": _iso_datetime(latest_tutor_run_at),
            "needs_supervision_refresh": needs_supervision_refresh(latest_tutor_run_at, mentor_updated_at),
        }
    return freshness


def choose_next_chapter(chapters: list[Any], mastery_records: dict[uuid.UUID, Any]) -> uuid.UUID | None:
    ordered_chapters = sorted(chapters, key=lambda chapter: getattr(chapter, "order_index", 0))
    for chapter in ordered_chapters:
        if _chapter_status(chapter) == ChapterStatus.active.value:
            mastery = mastery_records.get(chapter.id)
            if mastery is None or getattr(mastery, "score_percent", 0) < 70:
                return chapter.id
    for chapter in ordered_chapters:
        if _chapter_status(chapter) != ChapterStatus.completed.value:
            return chapter.id
    return None


def build_risk_chapters(
    chapters: list[Any],
    mastery_records: dict[uuid.UUID, Any],
    mentor_states: dict[uuid.UUID, Any],
    supervision_freshness: dict[uuid.UUID, dict[str, Any]] | None = None,
) -> list[dict]:
    risks: list[dict] = []
    supervision_freshness = supervision_freshness or {}
    for chapter in sorted(chapters, key=lambda item: getattr(item, "order_index", 0)):
        mastery = mastery_records.get(chapter.id)
        mentor = mentor_states.get(chapter.id)
        weak_points = list(getattr(mastery, "weak_points", []) or []) + list(getattr(mentor, "weak_points", []) or [])
        mentor_signal_count = _mentor_signal_count(mentor)
        score = getattr(mastery, "score_percent", None)
        needs_refresh = supervision_freshness.get(chapter.id, {}).get("needs_supervision_refresh") is True
        if score is not None and score < 70:
            risks.append(
                {
                    "chapter_id": str(chapter.id),
                    "title": chapter.title,
                    "reason": f"Mastery score is {score}%, below the review threshold.",
                    "score_percent": score,
                }
            )
        elif needs_refresh:
            risks.append(
                {
                    "chapter_id": str(chapter.id),
                    "title": chapter.title,
                    "reason": "New tutor signals need chapter mentor assessment.",
                    "score_percent": score,
                }
            )
        elif weak_points:
            risks.append(
                {
                    "chapter_id": str(chapter.id),
                    "title": chapter.title,
                    "reason": weak_points[0],
                    "score_percent": score,
                }
            )
        elif mentor_signal_count:
            risks.append(
                {
                    "chapter_id": str(chapter.id),
                    "title": chapter.title,
                    "reason": "Recent tutor signals indicate this chapter needs attention.",
                    "score_percent": score,
                }
            )
    return risks[:5]


def build_review_recommendations(
    chapters: list[Any],
    mastery_records: dict[uuid.UUID, Any],
    mentor_states: dict[uuid.UUID, Any],
    supervision_freshness: dict[uuid.UUID, dict[str, Any]] | None = None,
) -> list[dict]:
    recommendations: list[dict] = []
    supervision_freshness = supervision_freshness or {}
    for chapter in sorted(chapters, key=lambda item: getattr(item, "order_index", 0)):
        mastery = mastery_records.get(chapter.id)
        mentor = mentor_states.get(chapter.id)
        score = getattr(mastery, "score_percent", None)
        weak_points = list(getattr(mastery, "weak_points", []) or []) + list(getattr(mentor, "weak_points", []) or [])
        mentor_signal_count = _mentor_signal_count(mentor)
        needs_refresh = supervision_freshness.get(chapter.id, {}).get("needs_supervision_refresh") is True
        if score is not None and score < 70:
            recommendations.append(
                {
                    "chapter_id": str(chapter.id),
                    "title": chapter.title,
                    "action": "Retake chapter quiz after evidence review.",
                    "reason": f"Current mastery is {score}%.",
                }
            )
        elif needs_refresh:
            recommendations.append(
                {
                    "chapter_id": str(chapter.id),
                    "title": chapter.title,
                    "action": "Refresh chapter mentor assessment from recent tutor signals.",
                    "reason": "New tutor signals are newer than the chapter mentor assessment.",
                }
            )
        elif weak_points:
            recommendations.append(
                {
                    "chapter_id": str(chapter.id),
                    "title": chapter.title,
                    "action": "Review weak point with the chapter mentor.",
                    "reason": weak_points[0],
                }
            )
        elif mentor_signal_count:
            recommendations.append(
                {
                    "chapter_id": str(chapter.id),
                    "title": chapter.title,
                    "action": "Review recent tutor confusion signals with the chapter mentor.",
                    "reason": "Recent tutor signals indicate this chapter needs attention.",
                }
            )
    return recommendations[:5]


def build_route_adjustments(chapters: list[Any], mastery_records: dict[uuid.UUID, Any]) -> list[dict]:
    completed_count = sum(1 for chapter in chapters if _chapter_status(chapter) == ChapterStatus.completed.value)
    low_mastery = [
        chapter
        for chapter in chapters
        if (mastery := mastery_records.get(chapter.id)) is not None and getattr(mastery, "score_percent", 0) < 40
    ]
    adjustments: list[dict] = []
    if low_mastery:
        chapter = sorted(low_mastery, key=lambda item: getattr(item, "order_index", 0))[0]
        adjustments.append(
            {
                "kind": "insert_review",
                "chapter_id": str(chapter.id),
                "title": f"Review before continuing: {chapter.title}",
                "rationale": "Low mastery suggests adding a focused review checkpoint before new material.",
            }
        )
    if chapters and completed_count == len(chapters):
        adjustments.append(
            {
                "kind": "extend_route",
                "chapter_id": None,
                "title": "Generate an advanced follow-up route",
                "rationale": "All chapters are complete; the planner can propose deeper practice next.",
            }
        )
    return adjustments


def build_summary(study_space: StudySpace, chapters: list[Any], mastery_records: dict[uuid.UUID, Any]) -> str:
    completed_count = sum(1 for chapter in chapters if _chapter_status(chapter) == ChapterStatus.completed.value)
    scores = [record.score_percent for record in mastery_records.values()]
    average_score = round(sum(scores) / len(scores)) if scores else None
    if average_score is None:
        return f"{study_space.name}: {completed_count}/{len(chapters)} chapters complete. Start with the recommended chapter and generate quizzes as evidence accumulates."
    return (
        f"{study_space.name}: {completed_count}/{len(chapters)} chapters complete with "
        f"{average_score}% average mastery across submitted quizzes."
    )


def build_evidence(
    chapters: list[Any],
    mastery_records: dict[uuid.UUID, Any],
    mentor_states: dict[uuid.UUID, Any],
    supervision_freshness: dict[uuid.UUID, dict[str, Any]] | None = None,
) -> list[dict]:
    supervision_freshness = supervision_freshness or {}
    evidence: list[dict] = []
    for chapter in sorted(chapters, key=lambda item: getattr(item, "order_index", 0)):
        item = {
            "chapter_id": str(chapter.id),
            "title": chapter.title,
            "status": _chapter_status(chapter),
            "mastery_score": getattr(mastery_records.get(chapter.id), "score_percent", None),
            "mastery_level": _mastery_level(mastery_records[chapter.id]) if chapter.id in mastery_records else None,
            "mentor_weak_points": list(getattr(mentor_states.get(chapter.id), "weak_points", []) or []),
            "mentor_signal_count": _mentor_signal_count(mentor_states.get(chapter.id)),
        }
        item.update(supervision_freshness.get(chapter.id, {}))
        evidence.append(item)
    return evidence


def build_space_planner_state_response(state: SpacePlannerState) -> SpacePlannerStateResponse:
    return SpacePlannerStateResponse(
        id=state.id,
        study_space_id=state.study_space_id,
        summary=state.summary,
        next_chapter_id=state.next_chapter_id,
        risk_chapters=[PlannerChapterRisk(**item) for item in state.risk_chapters or []],
        review_recommendations=[PlannerReviewRecommendation(**item) for item in state.review_recommendations or []],
        route_adjustments=[PlannerRouteAdjustment(**item) for item in state.route_adjustments or []],
        evidence=state.evidence or [],
        updated_at=state.updated_at,
    )


async def ensure_study_space_for_planner(
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


async def build_space_planner_snapshot(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> tuple[StudySpace, list[Chapter], dict[uuid.UUID, MasteryRecord], dict[uuid.UUID, ChapterMentorState]]:
    study_space = await ensure_study_space_for_planner(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
    )
    route = await session.scalar(
        select(LearningRoute).where(
            LearningRoute.tenant_id == tenant_id,
            LearningRoute.study_space_id == study_space_id,
            LearningRoute.status == LearningRouteStatus.active,
        )
    )
    if route is None:
        raise ValueError("Active route not found")

    chapter_rows = await session.scalars(
        select(Chapter)
        .where(
            Chapter.tenant_id == tenant_id,
            Chapter.study_space_id == study_space_id,
            Chapter.learning_route_id == route.id,
        )
        .order_by(Chapter.order_index)
    )
    chapters = list(chapter_rows)

    mastery_rows = await session.scalars(
        select(MasteryRecord).where(
            MasteryRecord.tenant_id == tenant_id,
            MasteryRecord.user_id == user_id,
            MasteryRecord.study_space_id == study_space_id,
        )
    )
    mastery_records = {record.chapter_id: record for record in mastery_rows}

    mentor_rows = await session.scalars(
        select(ChapterMentorState).where(
            ChapterMentorState.tenant_id == tenant_id,
            ChapterMentorState.study_space_id == study_space_id,
        )
    )
    mentor_states = {state.chapter_id: state for state in mentor_rows}
    return study_space, chapters, mastery_records, mentor_states


async def load_latest_session_tutor_run_times(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> dict[uuid.UUID, datetime]:
    rows = await session.execute(
        select(AgentRun, Session)
        .join(Session, AgentRun.session_id == Session.id)
        .where(
            AgentRun.tenant_id == tenant_id,
            AgentRun.study_space_id == study_space_id,
            AgentRun.agent_type == AgentType.session_tutor,
            AgentRun.status == AgentRunStatus.completed,
            Session.tenant_id == tenant_id,
            Session.study_space_id == study_space_id,
        )
        .order_by(AgentRun.completed_at.desc().nulls_last(), AgentRun.created_at.desc(), AgentRun.id)
    )
    latest_by_chapter: dict[uuid.UUID, datetime] = {}
    for run, tutor_session in rows.all():
        if tutor_session.chapter_id in latest_by_chapter:
            continue
        run_at = run.completed_at or run.created_at
        if run_at is not None:
            latest_by_chapter[tutor_session.chapter_id] = run_at
    return latest_by_chapter


async def get_space_planner_state(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> SpacePlannerState | None:
    await ensure_study_space_for_planner(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
    )
    return await session.scalar(
        select(SpacePlannerState).where(
            SpacePlannerState.tenant_id == tenant_id,
            SpacePlannerState.user_id == user_id,
            SpacePlannerState.study_space_id == study_space_id,
        )
    )


async def generate_space_planner_state(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> SpacePlannerStateResponse:
    study_space, chapters, mastery_records, mentor_states = await build_space_planner_snapshot(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
    )
    latest_tutor_runs = await load_latest_session_tutor_run_times(
        session=session,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
    )
    supervision_freshness = build_supervision_freshness(chapters, mentor_states, latest_tutor_runs)
    state = await session.scalar(
        select(SpacePlannerState).where(
            SpacePlannerState.tenant_id == tenant_id,
            SpacePlannerState.user_id == user_id,
            SpacePlannerState.study_space_id == study_space_id,
        )
    )
    if state is None:
        state = SpacePlannerState(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            study_space_id=study_space_id,
            summary="",
            risk_chapters=[],
            review_recommendations=[],
            route_adjustments=[],
            evidence=[],
        )
        session.add(state)

    state.summary = build_summary(study_space, chapters, mastery_records)
    state.next_chapter_id = choose_next_chapter(chapters, mastery_records)
    state.risk_chapters = build_risk_chapters(chapters, mastery_records, mentor_states, supervision_freshness)
    state.review_recommendations = build_review_recommendations(
        chapters,
        mastery_records,
        mentor_states,
        supervision_freshness,
    )
    state.route_adjustments = build_route_adjustments(chapters, mastery_records)
    state.evidence = build_evidence(chapters, mastery_records, mentor_states, supervision_freshness)
    state.updated_at = datetime.now(UTC)

    session.add(
        AgentRun(
            tenant_id=tenant_id,
            study_space_id=study_space_id,
            session_id=None,
            message_id=None,
            agent_type=AgentType.space_planner,
            status=AgentRunStatus.completed,
            model="deterministic",
            input_payload={
                "study_space_id": str(study_space_id),
                "chapter_count": len(chapters),
                "mastery_count": len(mastery_records),
            },
            output_payload={
                "state_id": str(state.id),
                "next_chapter_id": str(state.next_chapter_id) if state.next_chapter_id else None,
                "risk_count": len(state.risk_chapters),
            },
            completed_at=datetime.now(UTC),
        )
    )

    await session.commit()
    await session.refresh(state)
    return build_space_planner_state_response(state)
