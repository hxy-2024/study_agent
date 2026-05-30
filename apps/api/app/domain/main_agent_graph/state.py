from typing import Any, Literal, NotRequired, TypedDict

from app.domain.dashboard.schemas import DashboardRecommendation, DashboardRecommendationRequest


MainAgentRouteDecision = Literal["create_space", "review", "quiz", "new_material", "balanced"]


class MainAgentGraphState(TypedDict):
    spaces: list[Any]
    chapters: list[Any]
    planner_actions: list[Any]
    mastery_records: list[Any]
    quizzes: list[Any]
    review_candidates: list[Any]
    quiz_mastery_signals: list[Any]
    review_queue: list[Any]
    request: DashboardRecommendationRequest
    node_trace: list[str]
    tool_calls: list[str]
    signal_counts: NotRequired[dict[str, int]]
    route_decision: NotRequired[MainAgentRouteDecision]
    recommendation: NotRequired[DashboardRecommendation]
