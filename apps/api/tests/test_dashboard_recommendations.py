import uuid
from types import SimpleNamespace

from app.domain.dashboard.recommendations import build_main_agent_recommendation


def test_main_agent_recommends_active_chapter_first() -> None:
    space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    recommendation = build_main_agent_recommendation(
        spaces=[
            SimpleNamespace(id=space_id, name="RAG Basics", status="active", target_days=14),
        ],
        chapters=[
            SimpleNamespace(
                id=chapter_id,
                study_space_id=space_id,
                title="Retrieval",
                status="active",
                order_index=1,
            )
        ],
        planner_actions=[],
        mastery_records=[],
    )

    assert recommendation is not None
    assert recommendation.agent_type == "main_agent"
    assert recommendation.recommendation_type == "continue_chapter"
    assert recommendation.title == "Continue Retrieval"
    assert recommendation.action_url == f"/chapters/{chapter_id}"
    assert recommendation.study_space_id == space_id
    assert recommendation.chapter_id == chapter_id
    assert recommendation.freshness == "deterministic_fallback"


def test_main_agent_recommends_create_space_when_no_space_exists() -> None:
    recommendation = build_main_agent_recommendation(
        spaces=[],
        chapters=[],
        planner_actions=[],
        mastery_records=[],
    )

    assert recommendation is not None
    assert recommendation.recommendation_type == "create_space"
    assert recommendation.action_url == "/spaces/new"
    assert recommendation.action_label == "Create space"
