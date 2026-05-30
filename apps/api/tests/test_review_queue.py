import uuid
from types import SimpleNamespace

from app.domain.quiz_mastery.schemas import QuizMasterySignal
from app.domain.review_planner.schemas import ReviewCandidate
from app.domain.review_queue.service import build_review_queue


def test_review_queue_prioritizes_review_candidate_before_continue_chapter() -> None:
    study_space_id = uuid.uuid4()
    review_chapter_id = uuid.uuid4()
    continue_chapter_id = uuid.uuid4()

    queue = build_review_queue(
        chapters=[
            SimpleNamespace(
                id=review_chapter_id,
                study_space_id=study_space_id,
                title="Grounding",
                status="completed",
                order_index=1,
            ),
            SimpleNamespace(
                id=continue_chapter_id,
                study_space_id=study_space_id,
                title="Embeddings",
                status="active",
                order_index=2,
            ),
        ],
        review_candidates=[
            ReviewCandidate(
                study_space_id=study_space_id,
                chapter_id=review_chapter_id,
                title="Review Grounding",
                reason="Review weak point: source grounding.",
                score=92,
                weak_points=["source grounding"],
                source="mastery",
            )
        ],
    )

    assert queue[0].kind == "review_chapter"
    assert queue[0].chapter_id == review_chapter_id
    assert queue[0].priority == 92
    assert queue[0].action_url == f"/chapters/{review_chapter_id}"
    assert queue[1].kind == "continue_chapter"
    assert queue[1].chapter_id == continue_chapter_id


def test_review_queue_adds_quiz_retake_with_quiz_url() -> None:
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    quiz_id = uuid.uuid4()

    queue = build_review_queue(
        chapters=[
            SimpleNamespace(
                id=chapter_id,
                study_space_id=study_space_id,
                title="Retrieval",
                status="completed",
                order_index=1,
            )
        ],
        quizzes=[
            SimpleNamespace(
                id=quiz_id,
                study_space_id=study_space_id,
                chapter_id=chapter_id,
            )
        ],
        quiz_mastery_signals=[
            QuizMasterySignal(
                study_space_id=study_space_id,
                chapter_id=chapter_id,
                attempt_count=2,
                latest_score=60,
                trend="declining",
                weak_points=["citation grounding"],
                retake_recommended=True,
                reason="Retake recommended after 60% latest score.",
                latest_submission_id=uuid.uuid4(),
            )
        ],
    )

    assert queue[0].kind == "retake_quiz"
    assert queue[0].quiz_id == quiz_id
    assert queue[0].action_url == f"/quizzes/{quiz_id}"
    assert queue[0].source_signals["quiz_mastery"] == 1
