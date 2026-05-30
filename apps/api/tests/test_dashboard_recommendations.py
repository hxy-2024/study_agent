import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.db.models import AgentType
from app.domain.dashboard.schemas import DashboardRecommendationRequest
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


def test_main_agent_is_registered_agent_type() -> None:
    assert AgentType.main_agent.value == "main_agent"
    assert AgentType.review_planner.value == "review_planner"
    assert AgentType.quiz_mastery.value == "quiz_mastery"


def test_main_agent_review_intent_prefers_low_mastery() -> None:
    space_id = uuid.uuid4()
    weak_chapter_id = uuid.uuid4()
    new_chapter_id = uuid.uuid4()

    recommendation = build_main_agent_recommendation(
        spaces=[SimpleNamespace(id=space_id, name="Algorithms", status="active", target_days=30)],
        chapters=[
            SimpleNamespace(
                id=new_chapter_id,
                study_space_id=space_id,
                title="Graphs",
                status="not_started",
                order_index=1,
            ),
            SimpleNamespace(
                id=weak_chapter_id,
                study_space_id=space_id,
                title="Dynamic Programming",
                status="completed",
                order_index=2,
            ),
        ],
        planner_actions=[],
        mastery_records=[
            SimpleNamespace(
                chapter_id=weak_chapter_id,
                study_space_id=space_id,
                score_percent=48,
                level="developing",
                weak_points=["state transitions"],
                updated_at=datetime.now(UTC) - timedelta(days=8),
            )
        ],
        request=DashboardRecommendationRequest(available_minutes=15, intent="review"),
    )

    assert recommendation is not None
    assert recommendation.recommendation_type == "review_chapter"
    assert recommendation.chapter_id == weak_chapter_id
    assert recommendation.estimated_minutes == 15
    assert recommendation.strategy_version == "main_agent_agenda_v2"
    assert "mastery" in recommendation.source_signals


def test_main_agent_new_material_intent_prefers_unfinished_chapter() -> None:
    space_id = uuid.uuid4()
    weak_chapter_id = uuid.uuid4()
    new_chapter_id = uuid.uuid4()

    recommendation = build_main_agent_recommendation(
        spaces=[SimpleNamespace(id=space_id, name="Algorithms", status="active", target_days=30)],
        chapters=[
            SimpleNamespace(
                id=new_chapter_id,
                study_space_id=space_id,
                title="Graphs",
                status="not_started",
                order_index=1,
            ),
            SimpleNamespace(
                id=weak_chapter_id,
                study_space_id=space_id,
                title="Dynamic Programming",
                status="completed",
                order_index=2,
            ),
        ],
        planner_actions=[],
        mastery_records=[
            SimpleNamespace(
                chapter_id=weak_chapter_id,
                study_space_id=space_id,
                score_percent=45,
                level="developing",
                weak_points=["state transitions"],
                updated_at=datetime.now(UTC) - timedelta(days=8),
            )
        ],
        request=DashboardRecommendationRequest(available_minutes=60, intent="new_material"),
    )

    assert recommendation is not None
    assert recommendation.recommendation_type == "continue_chapter"
    assert recommendation.chapter_id == new_chapter_id
    assert recommendation.estimated_minutes == 45
