from typing import Any

from app.db.models import ChapterStatus, PlannerActionStatus, QuizStatus
from app.domain.dashboard.schemas import DashboardRecommendation, DashboardRecommendationAction, DashboardRecommendationRequest
from app.domain.quiz_mastery.schemas import QuizMasterySignal
from app.domain.review_planner.schemas import ReviewCandidate
from app.domain.review_queue.schemas import ReviewQueueItem


STRATEGY_VERSION = "main_agent_agenda_v2"


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _space_name(spaces: list[Any], study_space_id: Any) -> str:
    for space in spaces:
        if space.id == study_space_id:
            return getattr(space, "name", "this space")
    return "this space"


def _chapter_action(chapter: Any, spaces: list[Any], reason: str) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=f"Continue {chapter.title}",
        action_label="Study now",
        action_url=f"/chapters/{chapter.id}",
        recommendation_type="continue_chapter",
        reason=reason,
        estimated_minutes=25,
        study_space_id=chapter.study_space_id,
        chapter_id=chapter.id,
    )


def _review_action(chapter: Any, spaces: list[Any], mastery: Any, available_minutes: int) -> DashboardRecommendationAction:
    weak_points = getattr(mastery, "weak_points", []) or []
    reason = "This chapter has low or stale mastery."
    if weak_points:
        reason = f"Review weak point: {weak_points[0]}."
    return DashboardRecommendationAction(
        title=f"Review {chapter.title}",
        action_label="Review now",
        action_url=f"/chapters/{chapter.id}",
        recommendation_type="review_chapter",
        reason=reason,
        estimated_minutes=min(20, available_minutes),
        study_space_id=chapter.study_space_id,
        chapter_id=chapter.id,
    )


def _review_candidate_action(candidate: ReviewCandidate, available_minutes: int) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=candidate.title,
        action_label="Review now",
        action_url=f"/chapters/{candidate.chapter_id}",
        recommendation_type="review_chapter",
        reason=candidate.reason,
        estimated_minutes=min(20, available_minutes),
        study_space_id=candidate.study_space_id,
        chapter_id=candidate.chapter_id,
    )


def _quiz_action(chapter: Any, quiz: Any, available_minutes: int) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=f"Quiz yourself on {chapter.title}",
        action_label="Start quiz",
        action_url=f"/quizzes/{quiz.id}",
        recommendation_type="quiz_chapter",
        reason="A quiz is ready for this chapter.",
        estimated_minutes=min(15, available_minutes),
        study_space_id=chapter.study_space_id,
        chapter_id=chapter.id,
    )


def _quiz_mastery_action(signal: QuizMasterySignal, quizzes: list[Any], available_minutes: int) -> DashboardRecommendationAction:
    quiz = next((item for item in quizzes if item.chapter_id == signal.chapter_id), None)
    action_url = f"/quizzes/{quiz.id}" if quiz is not None else f"/chapters/{signal.chapter_id}"
    return DashboardRecommendationAction(
        title="Retake quiz",
        action_label="Retake quiz",
        action_url=action_url,
        recommendation_type="retake_quiz",
        reason=signal.reason,
        estimated_minutes=min(15, available_minutes),
        study_space_id=signal.study_space_id,
        chapter_id=signal.chapter_id,
    )


def _planner_action(action: Any) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=action.title,
        action_label="Review action",
        action_url=f"/chapters/{action.chapter_id}" if action.chapter_id else f"/spaces/{action.study_space_id}",
        recommendation_type="planner_action",
        reason="Your planner has an open recommendation.",
        estimated_minutes=15,
        study_space_id=action.study_space_id,
        chapter_id=action.chapter_id,
    )


def _queue_action(item: ReviewQueueItem) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=item.title,
        action_label=(
            "Retake quiz"
            if item.kind == "retake_quiz"
            else "Review now"
            if item.kind == "review_chapter"
            else "Study now"
        ),
        action_url=item.action_url,
        recommendation_type=item.kind,
        reason=item.reason,
        estimated_minutes=item.estimated_minutes,
        study_space_id=item.study_space_id,
        chapter_id=item.chapter_id,
    )


def _prepare_space_action(space: Any) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=f"Prepare a route for {space.name}",
        action_label="Open space",
        action_url=f"/spaces/{space.id}",
        recommendation_type="prepare_route",
        reason="This study space is active but does not have a chapter queue yet.",
        estimated_minutes=10,
        study_space_id=space.id,
    )


def _find_chapter(chapters: list[Any], chapter_id: Any) -> Any | None:
    for chapter in chapters:
        if chapter.id == chapter_id:
            return chapter
    return None


def _is_weak_mastery(mastery: Any) -> bool:
    score = getattr(mastery, "score_percent", 100)
    level = _enum_value(getattr(mastery, "level", "mastered"))
    return score < 70 or level in {"new", "developing"}


def _source_signals(
    *,
    spaces: list[Any],
    chapters: list[Any],
    planner_actions: list[Any],
    mastery_records: list[Any],
    quizzes: list[Any],
) -> dict[str, int]:
    return {
        "spaces": len(spaces),
        "chapters": len(chapters),
        "planner_actions": len(planner_actions),
        "mastery": len(mastery_records),
        "quizzes": len(quizzes),
    }


def build_main_agent_recommendation(
    *,
    spaces: list[Any],
    chapters: list[Any],
    planner_actions: list[Any],
    mastery_records: list[Any],
    quizzes: list[Any] | None = None,
    review_candidates: list[ReviewCandidate] | None = None,
    quiz_mastery_signals: list[QuizMasterySignal] | None = None,
    review_queue: list[ReviewQueueItem] | None = None,
    request: DashboardRecommendationRequest | None = None,
) -> DashboardRecommendation | None:
    request = request or DashboardRecommendationRequest()
    quizzes = quizzes or []
    review_candidates = review_candidates or []
    quiz_mastery_signals = quiz_mastery_signals or []
    review_queue = review_queue or []
    candidates: list[DashboardRecommendationAction] = []
    review_actions: list[DashboardRecommendationAction] = [
        _review_candidate_action(candidate, request.available_minutes) for candidate in review_candidates
    ]
    quiz_candidates: list[DashboardRecommendationAction] = []
    quiz_mastery_candidates: list[DashboardRecommendationAction] = [
        _quiz_mastery_action(signal, quizzes, request.available_minutes)
        for signal in quiz_mastery_signals
        if signal.retake_recommended
    ]
    chapter_candidates: list[DashboardRecommendationAction] = []
    source_signals = _source_signals(
        spaces=spaces,
        chapters=chapters,
        planner_actions=planner_actions,
        mastery_records=mastery_records,
        quizzes=quizzes,
    )
    source_signals["review_candidates"] = len(review_candidates)
    source_signals["quiz_mastery"] = len(quiz_mastery_signals)
    source_signals["review_queue"] = len(review_queue)

    for mastery in sorted(
        [record for record in mastery_records if _is_weak_mastery(record)],
        key=lambda record: (getattr(record, "score_percent", 100), str(record.chapter_id)),
    ):
        chapter = _find_chapter(chapters, mastery.chapter_id)
        if chapter is not None:
            review_actions.append(_review_action(chapter, spaces, mastery, request.available_minutes))

    active_quizzes = [
        quiz for quiz in quizzes if _enum_value(getattr(quiz, "status", "")) in {QuizStatus.active.value, QuizStatus.submitted.value}
    ]
    for quiz in sorted(active_quizzes, key=lambda item: (str(item.study_space_id), str(item.chapter_id), str(item.id))):
        chapter = _find_chapter(chapters, quiz.chapter_id)
        if chapter is not None:
            quiz_candidates.append(_quiz_action(chapter, quiz, request.available_minutes))

    active_or_next = sorted(
        [
            chapter
            for chapter in chapters
            if _enum_value(getattr(chapter, "status", "")) != ChapterStatus.completed.value
        ],
        key=lambda chapter: (str(chapter.study_space_id), chapter.order_index, str(chapter.id)),
    )
    for chapter in active_or_next:
        reason = f"{_space_name(spaces, chapter.study_space_id)} has an unfinished chapter ready."
        action = _chapter_action(chapter, spaces, reason)
        action.estimated_minutes = min(45, request.available_minutes)
        chapter_candidates.append(action)

    open_actions = [
        action
        for action in planner_actions
        if _enum_value(getattr(action, "status", ""))
        in {PlannerActionStatus.proposed.value, PlannerActionStatus.accepted.value}
    ]
    planner_candidates = [_planner_action(action) for action in open_actions]
    queue_candidates = [_queue_action(item) for item in review_queue]
    if request.intent == "review":
        queue_candidates = [
            action
            for action in queue_candidates
            if action.recommendation_type in {"review_chapter", "retake_quiz", "planner_action"}
        ] + [
            action
            for action in queue_candidates
            if action.recommendation_type == "continue_chapter"
        ]
    elif request.intent == "quiz":
        quiz_queue_candidates = [
            action
            for action in queue_candidates
            if action.recommendation_type == "retake_quiz"
        ]
        other_queue_candidates = [
            action
            for action in queue_candidates
            if action.recommendation_type != "retake_quiz"
        ]

    if request.intent == "review":
        candidates = queue_candidates + review_actions + quiz_mastery_candidates + chapter_candidates + quiz_candidates + planner_candidates
    elif request.intent == "quiz":
        candidates = (
            quiz_queue_candidates
            + quiz_mastery_candidates
            + quiz_candidates
            + other_queue_candidates
            + review_actions
            + chapter_candidates
            + planner_candidates
        )
    elif request.intent == "new_material":
        candidates = queue_candidates + chapter_candidates + review_actions + quiz_mastery_candidates + quiz_candidates + planner_candidates
    else:
        candidates = queue_candidates + review_actions + quiz_mastery_candidates + chapter_candidates + quiz_candidates + planner_candidates

    if not candidates and spaces:
        candidates.append(_prepare_space_action(spaces[0]))

    if not candidates:
        return DashboardRecommendation(
            title="Create your first study space",
            action_label="Create space",
            action_url="/spaces/new",
            recommendation_type="create_space",
            reason="No active learning space exists yet.",
            estimated_minutes=10,
            strategy_version=STRATEGY_VERSION,
            source_signals=source_signals,
        )

    primary = candidates[0]
    return DashboardRecommendation(
        **primary.model_dump(),
        strategy_version=STRATEGY_VERSION,
        source_signals=source_signals,
        secondary_actions=candidates[1:4],
    )
