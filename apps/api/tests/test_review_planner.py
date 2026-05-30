import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.domain.review_planner.service import build_review_candidates


def _chapter(chapter_id, study_space_id, title="Retrieval", status="completed", order_index=1):
    return SimpleNamespace(
        id=chapter_id,
        study_space_id=study_space_id,
        title=title,
        status=status,
        order_index=order_index,
    )


def test_low_mastery_creates_high_priority_review_candidate() -> None:
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    candidates = build_review_candidates(
        chapters=[_chapter(chapter_id, study_space_id)],
        mastery_records=[
            SimpleNamespace(
                chapter_id=chapter_id,
                study_space_id=study_space_id,
                score_percent=52,
                level="developing",
                weak_points=["source grounding"],
                updated_at=datetime.now(UTC),
            )
        ],
    )

    assert len(candidates) == 1
    assert candidates[0].chapter_id == chapter_id
    assert candidates[0].study_space_id == study_space_id
    assert candidates[0].title == "Review Retrieval"
    assert candidates[0].reason == "Review weak point: source grounding."
    assert candidates[0].score == 100
    assert candidates[0].source == "mastery"


def test_stale_mastery_creates_review_candidate() -> None:
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    candidates = build_review_candidates(
        chapters=[_chapter(chapter_id, study_space_id)],
        mastery_records=[
            SimpleNamespace(
                chapter_id=chapter_id,
                study_space_id=study_space_id,
                score_percent=88,
                level="proficient",
                weak_points=[],
                updated_at=datetime.now(UTC) - timedelta(days=9),
            )
        ],
    )

    assert len(candidates) == 1
    assert candidates[0].reason == "This chapter has not been reviewed recently."
    assert candidates[0].score == 72
    assert candidates[0].source == "stale_mastery"


def test_completed_chapter_without_mastery_is_lower_priority() -> None:
    study_space_id = uuid.uuid4()
    known_chapter_id = uuid.uuid4()
    missing_chapter_id = uuid.uuid4()

    candidates = build_review_candidates(
        chapters=[
            _chapter(known_chapter_id, study_space_id, title="Known", order_index=1),
            _chapter(missing_chapter_id, study_space_id, title="Missing", order_index=2),
        ],
        mastery_records=[
            SimpleNamespace(
                chapter_id=known_chapter_id,
                study_space_id=study_space_id,
                score_percent=95,
                level="mastered",
                weak_points=[],
                updated_at=datetime.now(UTC),
            )
        ],
    )

    assert len(candidates) == 1
    assert candidates[0].chapter_id == missing_chapter_id
    assert candidates[0].reason == "This completed chapter has not been checked for retention yet."
    assert candidates[0].score == 40
    assert candidates[0].source == "missing_mastery"
