from typing import Any

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Chapter,
    LearningSignal,
    LearningSignalStatus,
    MasteryRecord,
    PlannerAction,
    PlannerActionStatus,
    Quiz,
    QuizSubmission,
    StudySpace,
    StudySpaceStatus,
)
from app.domain.learning_signals.service import list_active_learning_signals
from app.domain.quiz_mastery.schemas import QuizMasterySignal
from app.domain.quiz_mastery.service import build_quiz_mastery_signals
from app.domain.review_planner.schemas import ReviewCandidate
from app.domain.review_planner.service import build_review_candidates
from app.domain.review_queue.schemas import ReviewQueueItem


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _quiz_for_chapter(quizzes: list[Any], chapter_id: Any) -> Any | None:
    return next((quiz for quiz in quizzes if quiz.chapter_id == chapter_id), None)


def _queue_item_from_learning_signal(signal: LearningSignal, quizzes: list[Any]) -> ReviewQueueItem | None:
    payload = signal.payload or {}
    signal_type = signal.signal_type
    if signal_type == "review_chapter":
        chapter_id = signal.chapter_id
        if chapter_id is None:
            return None
        return ReviewQueueItem(
            id=signal.dedupe_key,
            learning_signal_id=signal.id,
            kind="review_chapter",
            study_space_id=signal.study_space_id,
            chapter_id=chapter_id,
            title=str(payload.get("title") or "Review chapter"),
            reason=str(payload.get("reason") or "This chapter is ready for review."),
            priority=signal.priority,
            estimated_minutes=20,
            action_url=f"/chapters/{chapter_id}",
            source_signals={"learning_signals": 1},
        )

    if signal_type == "retake_quiz":
        chapter_id = signal.chapter_id
        if chapter_id is None:
            return None
        quiz = _quiz_for_chapter(quizzes, chapter_id)
        quiz_id = getattr(quiz, "id", None) or signal.quiz_id
        return ReviewQueueItem(
            id=signal.dedupe_key,
            learning_signal_id=signal.id,
            kind="retake_quiz",
            study_space_id=signal.study_space_id,
            chapter_id=chapter_id,
            quiz_id=quiz_id,
            title="Retake quiz",
            reason=str(payload.get("reason") or "A quiz retake is recommended."),
            priority=signal.priority,
            estimated_minutes=15,
            action_url=f"/quizzes/{quiz_id}" if quiz_id is not None else f"/chapters/{chapter_id}",
            source_signals={"learning_signals": 1},
        )

    return None


def build_review_queue(
    *,
    chapters: list[Any],
    review_candidates: list[ReviewCandidate] | None = None,
    quiz_mastery_signals: list[QuizMasterySignal] | None = None,
    quizzes: list[Any] | None = None,
    planner_actions: list[Any] | None = None,
    learning_signals: list[LearningSignal] | None = None,
    suppressed_signal_keys: set[str] | None = None,
) -> list[ReviewQueueItem]:
    review_candidates = review_candidates or []
    quiz_mastery_signals = quiz_mastery_signals or []
    quizzes = quizzes or []
    planner_actions = planner_actions or []
    learning_signals = learning_signals or []
    suppressed_signal_keys = suppressed_signal_keys or set()
    items: list[ReviewQueueItem] = []
    durable_ids: set[str] = set()

    for signal in learning_signals:
        item = _queue_item_from_learning_signal(signal, quizzes)
        if item is None:
            continue
        durable_ids.add(item.id)
        items.append(item)

    for candidate in review_candidates:
        item_id = f"review:{candidate.chapter_id}:{candidate.source}"
        if item_id in durable_ids or item_id in suppressed_signal_keys:
            continue
        items.append(
            ReviewQueueItem(
                id=item_id,
                kind="review_chapter",
                study_space_id=candidate.study_space_id,
                chapter_id=candidate.chapter_id,
                title=candidate.title,
                reason=candidate.reason,
                priority=candidate.score,
                estimated_minutes=20,
                action_url=f"/chapters/{candidate.chapter_id}",
                source_signals={"review_candidates": 1},
            )
        )

    for signal in quiz_mastery_signals:
        if not signal.retake_recommended:
            continue
        item_id = f"quiz-retake:{signal.chapter_id}:{signal.latest_submission_id or 'none'}"
        if item_id in durable_ids or item_id in suppressed_signal_keys:
            continue
        quiz = _quiz_for_chapter(quizzes, signal.chapter_id)
        quiz_id = getattr(quiz, "id", None)
        items.append(
            ReviewQueueItem(
                id=item_id,
                kind="retake_quiz",
                study_space_id=signal.study_space_id,
                chapter_id=signal.chapter_id,
                quiz_id=quiz_id,
                title="Retake quiz",
                reason=signal.reason,
                priority=max(0, min(100, 100 - signal.latest_score + 40)),
                estimated_minutes=15,
                action_url=f"/quizzes/{quiz_id}" if quiz_id is not None else f"/chapters/{signal.chapter_id}",
                source_signals={"quiz_mastery": 1},
            )
        )

    for action in planner_actions:
        action_type = _enum_value(getattr(action, "action_type", "planner_action"))
        chapter_id = getattr(action, "chapter_id", None)
        study_space_id = action.study_space_id
        items.append(
            ReviewQueueItem(
                id=f"planner:{action.id}",
                kind="planner_action",
                study_space_id=study_space_id,
                chapter_id=chapter_id,
                title=action.title,
                reason=getattr(action, "rationale", "Your planner has an open recommendation."),
                priority=70 if action_type == "review_chapter" else 55,
                estimated_minutes=15,
                action_url=f"/chapters/{chapter_id}" if chapter_id else f"/spaces/{study_space_id}",
                source_signals={"planner_actions": 1},
            )
        )

    reviewed_chapter_ids = {item.chapter_id for item in items if item.chapter_id is not None}
    for chapter in chapters:
        if chapter.id in reviewed_chapter_ids:
            continue
        if _enum_value(getattr(chapter, "status", "")) == "completed":
            continue
        items.append(
            ReviewQueueItem(
                id=f"continue:{chapter.id}",
                kind="continue_chapter",
                study_space_id=chapter.study_space_id,
                chapter_id=chapter.id,
                title=f"Continue {chapter.title}",
                reason="This chapter is next in your active route.",
                priority=50,
                estimated_minutes=25,
                action_url=f"/chapters/{chapter.id}",
                source_signals={"chapters": 1},
            )
        )

    return sorted(items, key=lambda item: (-item.priority, item.kind, item.id))


async def get_review_queue(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    study_space_id: uuid.UUID | None = None,
) -> list[ReviewQueueItem]:
    active_space_ids_statement = select(StudySpace.id).where(
        StudySpace.tenant_id == tenant_id,
        StudySpace.owner_user_id == user_id,
        StudySpace.status != StudySpaceStatus.archived,
    )
    if study_space_id is not None:
        active_space_ids_statement = active_space_ids_statement.where(StudySpace.id == study_space_id)
    active_space_ids = active_space_ids_statement
    chapter_rows = await session.scalars(
        select(Chapter)
        .where(
            Chapter.tenant_id == tenant_id,
            Chapter.study_space_id.in_(active_space_ids),
        )
        .order_by(Chapter.study_space_id, Chapter.order_index, Chapter.id)
    )
    chapters = list(chapter_rows)
    mastery_rows = await session.scalars(
        select(MasteryRecord).where(
            MasteryRecord.tenant_id == tenant_id,
            MasteryRecord.user_id == user_id,
            MasteryRecord.study_space_id.in_(active_space_ids),
        )
    )
    mastery_records = list(mastery_rows)
    quiz_rows = await session.scalars(
        select(Quiz).where(
            Quiz.tenant_id == tenant_id,
            Quiz.user_id == user_id,
            Quiz.study_space_id.in_(active_space_ids),
        )
    )
    quizzes = list(quiz_rows)
    submission_rows = await session.scalars(
        select(QuizSubmission).where(
            QuizSubmission.tenant_id == tenant_id,
            QuizSubmission.user_id == user_id,
            QuizSubmission.chapter_id.in_(select(Chapter.id).where(Chapter.study_space_id.in_(active_space_ids))),
        )
    )
    submissions = list(submission_rows)
    action_rows = await session.scalars(
        select(PlannerAction)
        .where(
            PlannerAction.tenant_id == tenant_id,
            PlannerAction.user_id == user_id,
            PlannerAction.study_space_id.in_(active_space_ids),
            PlannerAction.status.in_([PlannerActionStatus.proposed, PlannerActionStatus.accepted]),
        )
        .order_by(PlannerAction.created_at.desc(), PlannerAction.id)
        .limit(20)
    )
    planner_actions = list(action_rows)
    signal_space_ids = sorted(
        {
            item.study_space_id
            for item in [*chapters, *quizzes, *planner_actions]
            if getattr(item, "study_space_id", None) is not None
        },
        key=str,
    )
    durable_signals = await list_active_learning_signals(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_ids=[study_space_id] if study_space_id is not None else signal_space_ids,
    )
    suppressed_signal_rows = await session.scalars(
        select(LearningSignal.dedupe_key).where(
            LearningSignal.tenant_id == tenant_id,
            LearningSignal.user_id == user_id,
            LearningSignal.study_space_id.in_([study_space_id] if study_space_id is not None else signal_space_ids),
            LearningSignal.status.in_(
                [
                    LearningSignalStatus.completed,
                    LearningSignalStatus.dismissed,
                    LearningSignalStatus.snoozed,
                ]
            ),
        )
    )
    suppressed_signal_keys = set(suppressed_signal_rows)

    return build_review_queue(
        chapters=chapters,
        learning_signals=durable_signals,
        suppressed_signal_keys=suppressed_signal_keys,
        review_candidates=build_review_candidates(chapters=chapters, mastery_records=mastery_records),
        quiz_mastery_signals=build_quiz_mastery_signals(
            chapters=chapters,
            mastery_records=mastery_records,
            submissions=submissions,
        ),
        quizzes=quizzes,
        planner_actions=planner_actions,
    )
