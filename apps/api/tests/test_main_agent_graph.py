import uuid
from types import SimpleNamespace

import pytest

from app.domain.dashboard.schemas import DashboardRecommendationRequest
from app.domain.main_agent_graph.service import run_main_agent_graph


@pytest.mark.anyio
async def test_main_agent_graph_routes_empty_workspace_to_create_space() -> None:
    result = await run_main_agent_graph(
        spaces=[],
        chapters=[],
        planner_actions=[],
        mastery_records=[],
        quizzes=[],
        review_candidates=[],
        quiz_mastery_signals=[],
        review_queue=[],
        request=DashboardRecommendationRequest(available_minutes=20, intent="balanced"),
    )

    assert result.recommendation.recommendation_type == "create_space"
    assert result.route_decision == "create_space"
    assert result.node_trace == ["inspect_context", "create_space_recommendation", "validate_recommendation"]
    assert result.tool_calls == []


@pytest.mark.anyio
async def test_main_agent_graph_chooses_review_tool_when_review_signals_exist() -> None:
    space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    result = await run_main_agent_graph(
        spaces=[SimpleNamespace(id=space_id, name="RAG", status="active", target_days=14)],
        chapters=[
            SimpleNamespace(
                id=chapter_id,
                study_space_id=space_id,
                title="Grounding",
                status="completed",
                order_index=1,
            )
        ],
        planner_actions=[],
        mastery_records=[
            SimpleNamespace(
                chapter_id=chapter_id,
                study_space_id=space_id,
                score_percent=52,
                level="developing",
                weak_points=["citations"],
            )
        ],
        quizzes=[],
        review_candidates=[],
        quiz_mastery_signals=[],
        review_queue=[],
        request=DashboardRecommendationRequest(available_minutes=15, intent="review"),
    )

    assert result.route_decision == "review"
    assert result.recommendation.recommendation_type == "review_chapter"
    assert result.recommendation.chapter_id == chapter_id
    assert result.node_trace == ["inspect_context", "choose_next_tool", "build_recommendation", "validate_recommendation"]
    assert result.tool_calls == ["build_main_agent_recommendation"]
    assert result.recommendation.freshness == "agentic_graph_v1"
    assert result.recommendation.strategy_version == "main_agent_graph_v1"
