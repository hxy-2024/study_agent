from datetime import UTC, datetime
from typing import Any

from app.db.models import ChapterStatus
from app.domain.review_planner.schemas import ReviewCandidate


STALE_REVIEW_DAYS = 7


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _age_days(value: datetime | None, now: datetime) -> int:
    updated_at = _as_aware_utc(value)
    if updated_at is None:
        return 0
    return max(0, (now - updated_at).days)


def _candidate_from_mastery(chapter: Any, mastery: Any, now: datetime) -> ReviewCandidate | None:
    score_percent = int(getattr(mastery, "score_percent", 100))
    level = _enum_value(getattr(mastery, "level", "mastered"))
    weak_points = list(getattr(mastery, "weak_points", []) or [])
    age_days = _age_days(getattr(mastery, "updated_at", None), now)

    if score_percent < 70 or level in {"new", "developing"}:
        reason = "This chapter has low mastery."
        if weak_points:
            reason = f"Review weak point: {weak_points[0]}."
        priority = min(100, 100 - score_percent + 52 + (12 if weak_points else 0))
        return ReviewCandidate(
            chapter_id=chapter.id,
            study_space_id=chapter.study_space_id,
            title=f"Review {chapter.title}",
            reason=reason,
            score=priority,
            weak_points=weak_points,
            source="mastery",
        )

    if age_days >= STALE_REVIEW_DAYS:
        priority = min(90, 45 + min(age_days * 3, 30))
        return ReviewCandidate(
            chapter_id=chapter.id,
            study_space_id=chapter.study_space_id,
            title=f"Review {chapter.title}",
            reason="This chapter has not been reviewed recently.",
            score=priority,
            weak_points=weak_points,
            source="stale_mastery",
        )

    return None


def build_review_candidates(
    *,
    chapters: list[Any],
    mastery_records: list[Any],
    now: datetime | None = None,
) -> list[ReviewCandidate]:
    now = _as_aware_utc(now) or datetime.now(UTC)
    mastery_by_chapter = {record.chapter_id: record for record in mastery_records}
    candidates: list[ReviewCandidate] = []

    for chapter in chapters:
        mastery = mastery_by_chapter.get(chapter.id)
        if mastery is not None:
            candidate = _candidate_from_mastery(chapter, mastery, now)
            if candidate is not None:
                candidates.append(candidate)
            continue

        if _enum_value(getattr(chapter, "status", "")) == ChapterStatus.completed.value:
            candidates.append(
                ReviewCandidate(
                    chapter_id=chapter.id,
                    study_space_id=chapter.study_space_id,
                    title=f"Review {chapter.title}",
                    reason="This completed chapter has not been checked for retention yet.",
                    score=40,
                    weak_points=[],
                    source="missing_mastery",
                )
            )

    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.title, str(candidate.chapter_id)))
