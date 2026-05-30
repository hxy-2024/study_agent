import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.db.models import AgentType
from app.domain.dashboard.schemas import DashboardRecommendationRequest
from app.domain.dashboard.recommendations import build_main_agent_recommendation
from app.domain.quiz_mastery.schemas import QuizMasterySignal
from app.domain.review_planner.schemas import ReviewCandidate


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


def test_main_agent_review_intent_uses_review_planner_candidate_first() -> None:
    space_id = uuid.uuid4()
    review_chapter_id = uuid.uuid4()
    new_chapter_id = uuid.uuid4()

    recommendation = build_main_agent_recommendation(
        spaces=[SimpleNamespace(id=space_id, name="RAG Basics", status="active", target_days=14)],
        chapters=[
            SimpleNamespace(
                id=new_chapter_id,
                study_space_id=space_id,
                title="New Retrieval",
                status="not_started",
                order_index=1,
            ),
            SimpleNamespace(
                id=review_chapter_id,
                study_space_id=space_id,
                title="Grounding",
                status="completed",
                order_index=2,
            ),
        ],
        planner_actions=[],
        mastery_records=[],
        review_candidates=[
            ReviewCandidate(
                chapter_id=review_chapter_id,
                study_space_id=space_id,
                title="Review Grounding",
                reason="Review weak point: citation drift.",
                score=100,
                weak_points=["citation drift"],
                source="mastery",
            )
        ],
        request=DashboardRecommendationRequest(available_minutes=30, intent="review"),
    )

    assert recommendation is not None
    assert recommendation.recommendation_type == "review_chapter"
    assert recommendation.chapter_id == review_chapter_id
    assert recommendation.reason == "Review weak point: citation drift."
    assert recommendation.source_signals["review_candidates"] == 1


def test_main_agent_balanced_intent_prefers_review_candidate_over_new_material() -> None:
    space_id = uuid.uuid4()
    review_chapter_id = uuid.uuid4()
    new_chapter_id = uuid.uuid4()

    recommendation = build_main_agent_recommendation(
        spaces=[SimpleNamespace(id=space_id, name="RAG Basics", status="active", target_days=14)],
        chapters=[
            SimpleNamespace(
                id=new_chapter_id,
                study_space_id=space_id,
                title="New Retrieval",
                status="not_started",
                order_index=1,
            )
        ],
        planner_actions=[],
        mastery_records=[],
        review_candidates=[
            ReviewCandidate(
                chapter_id=review_chapter_id,
                study_space_id=space_id,
                title="Review Grounding",
                reason="This chapter has not been reviewed recently.",
                score=72,
                weak_points=[],
                source="stale_mastery",
            )
        ],
        request=DashboardRecommendationRequest(available_minutes=30, intent="balanced"),
    )

    assert recommendation is not None
    assert recommendation.recommendation_type == "review_chapter"
    assert recommendation.chapter_id == review_chapter_id


def test_main_agent_quiz_intent_prefers_quiz_mastery_retake() -> None:
    space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    quiz_id = uuid.uuid4()

    recommendation = build_main_agent_recommendation(
        spaces=[SimpleNamespace(id=space_id, name="RAG Basics", status="active", target_days=14)],
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
        mastery_records=[],
        quizzes=[
            SimpleNamespace(
                id=quiz_id,
                study_space_id=space_id,
                chapter_id=chapter_id,
                status="submitted",
            )
        ],
        quiz_mastery_signals=[
            QuizMasterySignal(
                study_space_id=space_id,
                chapter_id=chapter_id,
                attempt_count=1,
                latest_score=62,
                trend="single_attempt",
                weak_points=["citation grounding"],
                retake_recommended=True,
                reason="Retake recommended after 62% latest score.",
            )
        ],
        request=DashboardRecommendationRequest(available_minutes=30, intent="quiz"),
    )

    assert recommendation is not None
    assert recommendation.recommendation_type == "retake_quiz"
    assert recommendation.action_url == f"/quizzes/{quiz_id}"
    assert recommendation.reason == "Retake recommended after 62% latest score."
    assert recommendation.source_signals["quiz_mastery"] == 1
