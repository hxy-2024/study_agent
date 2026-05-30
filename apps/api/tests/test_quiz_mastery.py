import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.domain.quiz_mastery.service import build_quiz_mastery_signals


def _chapter(chapter_id, study_space_id, title="Retrieval"):
    return SimpleNamespace(
        id=chapter_id,
        study_space_id=study_space_id,
        title=title,
    )


def _submission(chapter_id, study_space_id, score, *, weak_points=None, days_ago=0):
    return SimpleNamespace(
        id=uuid.uuid4(),
        chapter_id=chapter_id,
        study_space_id=study_space_id,
        score_percent=score,
        weak_points=weak_points or [],
        created_at=datetime.now(UTC) - timedelta(days=days_ago),
    )


def test_low_latest_score_recommends_quiz_retake() -> None:
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    signals = build_quiz_mastery_signals(
        chapters=[_chapter(chapter_id, study_space_id)],
        mastery_records=[],
        submissions=[
            _submission(chapter_id, study_space_id, 62, weak_points=["citation grounding"]),
        ],
    )

    assert len(signals) == 1
    assert signals[0].chapter_id == chapter_id
    assert signals[0].attempt_count == 1
    assert signals[0].latest_score == 62
    assert signals[0].trend == "single_attempt"
    assert signals[0].weak_points == ["citation grounding"]
    assert signals[0].retake_recommended is True
    assert signals[0].reason == "Retake recommended after 62% latest score."


def test_quiz_mastery_detects_improving_and_declining_trends() -> None:
    study_space_id = uuid.uuid4()
    improving_chapter_id = uuid.uuid4()
    declining_chapter_id = uuid.uuid4()

    signals = build_quiz_mastery_signals(
        chapters=[
            _chapter(improving_chapter_id, study_space_id, "Improving"),
            _chapter(declining_chapter_id, study_space_id, "Declining"),
        ],
        mastery_records=[],
        submissions=[
            _submission(improving_chapter_id, study_space_id, 58, days_ago=4),
            _submission(improving_chapter_id, study_space_id, 74, days_ago=1),
            _submission(declining_chapter_id, study_space_id, 90, days_ago=4),
            _submission(declining_chapter_id, study_space_id, 73, days_ago=1),
        ],
    )

    by_chapter = {signal.chapter_id: signal for signal in signals}

    assert by_chapter[improving_chapter_id].trend == "improving"
    assert by_chapter[improving_chapter_id].retake_recommended is False
    assert by_chapter[declining_chapter_id].trend == "declining"
    assert by_chapter[declining_chapter_id].retake_recommended is True


def test_quiz_mastery_uses_mastery_weak_points_when_latest_submission_has_none() -> None:
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    signals = build_quiz_mastery_signals(
        chapters=[_chapter(chapter_id, study_space_id)],
        mastery_records=[
            SimpleNamespace(
                chapter_id=chapter_id,
                weak_points=["retrieval recall"],
            )
        ],
        submissions=[
            _submission(chapter_id, study_space_id, 78, weak_points=[]),
        ],
    )

    assert len(signals) == 1
    assert signals[0].weak_points == ["retrieval recall"]
    assert signals[0].retake_recommended is True
    assert signals[0].reason == "Retake recommended for weak point: retrieval recall."
