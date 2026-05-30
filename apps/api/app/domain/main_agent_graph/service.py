from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, StateGraph

from app.domain.dashboard.schemas import DashboardRecommendation, DashboardRecommendationRequest
from app.domain.main_agent_graph import nodes
from app.domain.main_agent_graph.state import MainAgentGraphState


@dataclass(frozen=True)
class MainAgentGraphResult:
    recommendation: DashboardRecommendation
    node_trace: list[str]
    route_decision: str
    tool_calls: list[str]
    signal_counts: dict[str, int]


def _build_graph():
    graph_builder = StateGraph(MainAgentGraphState)
    graph_builder.add_node("inspect_context", nodes.inspect_context)
    graph_builder.add_node("choose_next_tool", nodes.choose_next_tool)
    graph_builder.add_node("create_space_recommendation", nodes.create_space_recommendation)
    graph_builder.add_node("build_recommendation", nodes.build_recommendation)
    graph_builder.add_node("validate_recommendation", nodes.validate_recommendation)

    graph_builder.set_entry_point("inspect_context")
    graph_builder.add_conditional_edges(
        "inspect_context",
        nodes.route_after_context,
        {
            "create_space_recommendation": "create_space_recommendation",
            "choose_next_tool": "choose_next_tool",
        },
    )
    graph_builder.add_conditional_edges(
        "choose_next_tool",
        nodes.route_after_tool_choice,
        {
            "review": "build_recommendation",
            "quiz": "build_recommendation",
            "new_material": "build_recommendation",
            "balanced": "build_recommendation",
        },
    )
    graph_builder.add_edge("create_space_recommendation", "validate_recommendation")
    graph_builder.add_edge("build_recommendation", "validate_recommendation")
    graph_builder.add_edge("validate_recommendation", END)
    return graph_builder.compile()


async def run_main_agent_graph(
    *,
    spaces: list[Any],
    chapters: list[Any],
    planner_actions: list[Any],
    mastery_records: list[Any],
    quizzes: list[Any],
    review_candidates: list[Any],
    quiz_mastery_signals: list[Any],
    review_queue: list[Any],
    request: DashboardRecommendationRequest,
) -> MainAgentGraphResult:
    graph = _build_graph()
    final_state = await graph.ainvoke(
        MainAgentGraphState(
            spaces=spaces,
            chapters=chapters,
            planner_actions=planner_actions,
            mastery_records=mastery_records,
            quizzes=quizzes,
            review_candidates=review_candidates,
            quiz_mastery_signals=quiz_mastery_signals,
            review_queue=review_queue,
            request=request,
            node_trace=[],
            tool_calls=[],
        )
    )
    return MainAgentGraphResult(
        recommendation=final_state["recommendation"],
        node_trace=final_state["node_trace"],
        route_decision=final_state["route_decision"],
        tool_calls=final_state["tool_calls"],
        signal_counts=final_state["signal_counts"],
    )
