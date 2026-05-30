import uuid

from app.domain.quiz_mastery.schemas import QuizMasterySignal
from app.domain.review_planner.schemas import ReviewCandidate
from app.domain.learning_signals.service import (
    learning_signal_from_quiz_mastery,
    learning_signal_from_review_candidate,
)


def test_learning_signal_from_review_candidate_has_stable_dedupe_key() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    candidate = ReviewCandidate(
        study_space_id=study_space_id,
        chapter_id=chapter_id,
        title="Review Retrieval",
        reason="Review weak point: source grounding.",
        score=100,
        weak_points=["source grounding"],
        source="mastery",
    )

    signal = learning_signal_from_review_candidate(
        candidate=candidate,
        tenant_id=tenant_id,
        user_id=user_id,
    )

    assert signal.tenant_id == tenant_id
    assert signal.user_id == user_id
    assert signal.study_space_id == study_space_id
    assert signal.chapter_id == chapter_id
    assert signal.quiz_id is None
    assert signal.agent_type == "review_planner"
    assert signal.signal_type == "review_chapter"
    assert signal.priority == 100
    assert signal.status == "active"
    assert signal.dedupe_key == f"review:{chapter_id}:mastery"
    assert signal.payload["title"] == "Review Retrieval"
    assert signal.payload["weak_points"] == ["source grounding"]


def test_learning_signal_from_quiz_mastery_uses_latest_submission_in_dedupe_key() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    submission_id = uuid.uuid4()
    signal = QuizMasterySignal(
        study_space_id=study_space_id,
        chapter_id=chapter_id,
        attempt_count=2,
        latest_score=62,
        trend="declining",
        weak_points=["citation grounding"],
        retake_recommended=True,
        reason="Retake recommended after 62% latest score.",
        latest_submission_id=submission_id,
    )

    learning_signal = learning_signal_from_quiz_mastery(
        signal=signal,
        tenant_id=tenant_id,
        user_id=user_id,
    )

    assert learning_signal.agent_type == "quiz_mastery"
    assert learning_signal.signal_type == "retake_quiz"
    assert learning_signal.priority == 78
    assert learning_signal.dedupe_key == f"quiz-retake:{chapter_id}:{submission_id}"
    assert learning_signal.payload["latest_score"] == 62
    assert learning_signal.payload["trend"] == "declining"
