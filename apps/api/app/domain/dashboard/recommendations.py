from typing import Any

from app.db.models import ChapterStatus, PlannerActionStatus
from app.domain.dashboard.schemas import DashboardRecommendation, DashboardRecommendationAction


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _space_name(spaces: list[Any], study_space_id: Any) -> str:
    for space in spaces:
        if space.id == study_space_id:
            return getattr(space, "name", "this space")
    return "this space"


def _chapter_action(chapter: Any, spaces: list[Any], reason: str) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=f"Continue {chapter.title}",
        action_label="Study now",
        action_url=f"/chapters/{chapter.id}",
        recommendation_type="continue_chapter",
        reason=reason,
        estimated_minutes=25,
        study_space_id=chapter.study_space_id,
        chapter_id=chapter.id,
    )


def _planner_action(action: Any) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=action.title,
        action_label="Review action",
        action_url=f"/chapters/{action.chapter_id}" if action.chapter_id else "/",
        recommendation_type="planner_action",
        reason="Your planner has an open recommendation.",
        estimated_minutes=15,
        study_space_id=action.study_space_id,
        chapter_id=action.chapter_id,
    )


def build_main_agent_recommendation(
    *,
    spaces: list[Any],
    chapters: list[Any],
    planner_actions: list[Any],
    mastery_records: list[Any],
) -> DashboardRecommendation | None:
    candidates: list[DashboardRecommendationAction] = []

    active_or_next = sorted(
        [
            chapter
            for chapter in chapters
            if _enum_value(getattr(chapter, "status", "")) != ChapterStatus.completed.value
        ],
        key=lambda chapter: (str(chapter.study_space_id), chapter.order_index, str(chapter.id)),
    )
    for chapter in active_or_next:
        reason = f"{_space_name(spaces, chapter.study_space_id)} has an unfinished chapter ready."
        candidates.append(_chapter_action(chapter, spaces, reason))

    open_actions = [
        action
        for action in planner_actions
        if _enum_value(getattr(action, "status", ""))
        in {PlannerActionStatus.proposed.value, PlannerActionStatus.accepted.value}
    ]
    candidates.extend(_planner_action(action) for action in open_actions)

    if not candidates:
        return DashboardRecommendation(
            title="Create your first study space",
            action_label="Create space",
            action_url="/spaces/new",
            recommendation_type="create_space",
            reason="No active learning space exists yet.",
            estimated_minutes=10,
        )

    primary = candidates[0]
    return DashboardRecommendation(
        **primary.model_dump(),
        secondary_actions=candidates[1:4],
    )
