from typing import Any

from app.db.models import ChapterStatus
from app.domain.dashboard.recommendations import build_main_agent_recommendation
from app.domain.dashboard.schemas import DashboardRecommendation
from app.domain.main_agent_graph.state import MainAgentGraphState, MainAgentRouteDecision


GRAPH_STRATEGY_VERSION = "main_agent_graph_v1"
GRAPH_FRESHNESS = "agentic_graph_v1"


def _trace(state: MainAgentGraphState, node_name: str) -> None:
    state.setdefault("node_trace", []).append(node_name)


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _has_unfinished_chapters(state: MainAgentGraphState) -> bool:
    return any(
        _enum_value(getattr(chapter, "status", "")) != ChapterStatus.completed.value
        for chapter in state["chapters"]
    )


def _has_review_signals(state: MainAgentGraphState) -> bool:
    if state["review_candidates"]:
        return True
    if any(
        getattr(item, "kind", "") in {"review_chapter", "retake_quiz", "planner_action"}
        for item in state["review_queue"]
    ):
        return True
    return any(
        getattr(record, "score_percent", 100) < 70
        or _enum_value(getattr(record, "level", "mastered")) in {"new", "developing"}
        for record in state["mastery_records"]
    )


def _has_quiz_signals(state: MainAgentGraphState) -> bool:
    return bool(state["quizzes"]) or any(
        getattr(signal, "retake_recommended", False)
        for signal in state["quiz_mastery_signals"]
    )


def inspect_context(state: MainAgentGraphState) -> MainAgentGraphState:
    _trace(state, "inspect_context")
    state["signal_counts"] = {
        "spaces": len(state["spaces"]),
        "chapters": len(state["chapters"]),
        "planner_actions": len(state["planner_actions"]),
        "mastery": len(state["mastery_records"]),
        "quizzes": len(state["quizzes"]),
        "review_candidates": len(state["review_candidates"]),
        "quiz_mastery": len(state["quiz_mastery_signals"]),
        "review_queue": len(state["review_queue"]),
    }
    return state


def route_after_context(state: MainAgentGraphState) -> str:
    return "create_space_recommendation" if not state["spaces"] else "choose_next_tool"


def choose_next_tool(state: MainAgentGraphState) -> MainAgentGraphState:
    _trace(state, "choose_next_tool")
    request = state["request"]
    route_decision: MainAgentRouteDecision
    if request.intent == "review" or _has_review_signals(state):
        route_decision = "review"
    elif request.intent == "quiz" or _has_quiz_signals(state):
        route_decision = "quiz"
    elif request.intent == "new_material" or _has_unfinished_chapters(state):
        route_decision = "new_material"
    else:
        route_decision = "balanced"
    state["route_decision"] = route_decision
    return state


def route_after_tool_choice(state: MainAgentGraphState) -> str:
    return state.get("route_decision", "balanced")


def create_space_recommendation(state: MainAgentGraphState) -> MainAgentGraphState:
    _trace(state, "create_space_recommendation")
    state["route_decision"] = "create_space"
    state["recommendation"] = DashboardRecommendation(
        title="Create your first study space",
        action_label="Create space",
        action_url="/spaces/new",
        recommendation_type="create_space",
        reason="No active learning space exists yet.",
        estimated_minutes=10,
        freshness=GRAPH_FRESHNESS,
        strategy_version=GRAPH_STRATEGY_VERSION,
        source_signals=state.get("signal_counts", {}),
    )
    return state


def build_recommendation(state: MainAgentGraphState) -> MainAgentGraphState:
    _trace(state, "build_recommendation")
    state.setdefault("tool_calls", []).append("build_main_agent_recommendation")
    recommendation = build_main_agent_recommendation(
        spaces=state["spaces"],
        chapters=state["chapters"],
        planner_actions=state["planner_actions"],
        mastery_records=state["mastery_records"],
        quizzes=state["quizzes"],
        review_candidates=state["review_candidates"],
        quiz_mastery_signals=state["quiz_mastery_signals"],
        review_queue=state["review_queue"],
        request=state["request"],
    )
    if recommendation is None:
        return create_space_recommendation(state)
    state["recommendation"] = recommendation.model_copy(
        update={
            "freshness": GRAPH_FRESHNESS,
            "strategy_version": GRAPH_STRATEGY_VERSION,
        }
    )
    return state


def validate_recommendation(state: MainAgentGraphState) -> MainAgentGraphState:
    _trace(state, "validate_recommendation")
    recommendation = state["recommendation"]
    available_minutes = state["request"].available_minutes
    if recommendation.estimated_minutes is not None and recommendation.estimated_minutes > available_minutes:
        state["recommendation"] = recommendation.model_copy(update={"estimated_minutes": available_minutes})
    return state
