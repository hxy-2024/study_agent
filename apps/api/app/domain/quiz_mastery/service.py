from datetime import datetime
from typing import Any

from app.domain.quiz_mastery.schemas import QuizMasterySignal, QuizMasteryTrend


TREND_DELTA = 10


def _chapter_space_id(chapters: list[Any], chapter_id: Any) -> Any | None:
    for chapter in chapters:
        if chapter.id == chapter_id:
            return chapter.study_space_id
    return None


def _mastery_weak_points(mastery_records: list[Any], chapter_id: Any) -> list[str]:
    for record in mastery_records:
        if record.chapter_id == chapter_id:
            return list(getattr(record, "weak_points", []) or [])
    return []


def _created_at(submission: Any) -> datetime:
    return getattr(submission, "created_at", None) or datetime.min


def _trend_for(attempts: list[Any]) -> QuizMasteryTrend:
    if len(attempts) == 1:
        return "single_attempt"
    latest = attempts[-1].score_percent
    previous = attempts[-2].score_percent
    if latest - previous >= TREND_DELTA:
        return "improving"
    if previous - latest >= TREND_DELTA:
        return "declining"
    return "flat"


def _reason_for(*, latest_score: int, trend: QuizMasteryTrend, weak_points: list[str], retake: bool) -> str:
    if not retake:
        if trend == "improving":
            return "Quiz trend is improving."
        return "Quiz mastery is on track."
    if latest_score < 70:
        return f"Retake recommended after {latest_score}% latest score."
    if trend == "declining":
        return "Retake recommended because quiz performance is declining."
    if weak_points:
        return f"Retake recommended for weak point: {weak_points[0]}."
    return "Retake recommended to confirm mastery."


def build_quiz_mastery_signals(
    *,
    chapters: list[Any],
    mastery_records: list[Any],
    submissions: list[Any],
) -> list[QuizMasterySignal]:
    attempts_by_chapter: dict[Any, list[Any]] = {}
    for submission in submissions:
        attempts_by_chapter.setdefault(submission.chapter_id, []).append(submission)

    signals: list[QuizMasterySignal] = []
    for chapter_id, attempts in attempts_by_chapter.items():
        attempts = sorted(attempts, key=lambda item: (_created_at(item), str(item.id)))
        latest = attempts[-1]
        study_space_id = getattr(latest, "study_space_id", None) or _chapter_space_id(chapters, chapter_id)
        if study_space_id is None:
            continue

        weak_points = list(getattr(latest, "weak_points", []) or []) or _mastery_weak_points(mastery_records, chapter_id)
        latest_score = int(latest.score_percent)
        trend = _trend_for(attempts)
        retake = latest_score < 70 or (trend == "declining" and latest_score < 85) or (bool(weak_points) and latest_score < 80)
        signals.append(
            QuizMasterySignal(
                study_space_id=study_space_id,
                chapter_id=chapter_id,
                attempt_count=len(attempts),
                latest_score=latest_score,
                trend=trend,
                weak_points=weak_points,
                retake_recommended=retake,
                reason=_reason_for(latest_score=latest_score, trend=trend, weak_points=weak_points, retake=retake),
                latest_submission_id=getattr(latest, "id", None),
                latest_submitted_at=getattr(latest, "created_at", None),
            )
        )

    return sorted(signals, key=lambda signal: (-int(signal.retake_recommended), signal.latest_score, str(signal.chapter_id)))
