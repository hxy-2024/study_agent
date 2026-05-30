import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentType, LearningSignal, LearningSignalStatus
from app.domain.learning_signals.schemas import LearningSignalDraft, LearningSignalResponse
from app.domain.quiz_mastery.schemas import QuizMasterySignal
from app.domain.review_planner.schemas import ReviewCandidate


def _status_value(status: LearningSignalStatus | str) -> str:
    return status.value if hasattr(status, "value") else str(status)


def build_learning_signal_response(signal: LearningSignal) -> LearningSignalResponse:
    return LearningSignalResponse(
        id=signal.id,
        tenant_id=signal.tenant_id,
        user_id=signal.user_id,
        study_space_id=signal.study_space_id,
        chapter_id=signal.chapter_id,
        quiz_id=signal.quiz_id,
        agent_type=signal.agent_type.value,
        signal_type=signal.signal_type,
        priority=signal.priority,
        status=_status_value(signal.status),
        dedupe_key=signal.dedupe_key,
        available_at=signal.available_at,
        expires_at=signal.expires_at,
        payload=signal.payload or {},
        created_at=signal.created_at,
        updated_at=signal.updated_at,
    )


def _agent_type(value: str) -> AgentType:
    try:
        return AgentType(value)
    except ValueError:
        return AgentType.session_tutor


def learning_signal_from_review_candidate(
    *,
    candidate: ReviewCandidate,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> LearningSignalDraft:
    return LearningSignalDraft(
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=candidate.study_space_id,
        chapter_id=candidate.chapter_id,
        agent_type="review_planner",
        signal_type="review_chapter",
        priority=candidate.score,
        dedupe_key=f"review:{candidate.chapter_id}:{candidate.source}",
        payload=candidate.model_dump(mode="json"),
    )


def learning_signal_from_quiz_mastery(
    *,
    signal: QuizMasterySignal,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> LearningSignalDraft:
    submission_key = signal.latest_submission_id or "none"
    priority = max(0, min(100, 100 - signal.latest_score + 40))
    return LearningSignalDraft(
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=signal.study_space_id,
        chapter_id=signal.chapter_id,
        agent_type="quiz_mastery",
        signal_type="retake_quiz" if signal.retake_recommended else "quiz_mastery",
        priority=priority,
        dedupe_key=f"quiz-retake:{signal.chapter_id}:{submission_key}",
        payload=signal.model_dump(mode="json"),
    )


async def upsert_learning_signal_drafts(
    *,
    session: AsyncSession,
    drafts: list[LearningSignalDraft],
) -> list[LearningSignal]:
    """Create or refresh durable signals by dedupe key without reactivating dismissed work."""
    results: list[LearningSignal] = []
    for draft in drafts:
        existing = await session.scalar(
            select(LearningSignal).where(
                LearningSignal.tenant_id == draft.tenant_id,
                LearningSignal.user_id == draft.user_id,
                LearningSignal.dedupe_key == draft.dedupe_key,
            )
        )
        if existing is None:
            signal = LearningSignal(
                tenant_id=draft.tenant_id,
                user_id=draft.user_id,
                study_space_id=draft.study_space_id,
                chapter_id=draft.chapter_id,
                quiz_id=draft.quiz_id,
                agent_type=_agent_type(draft.agent_type),
                signal_type=draft.signal_type,
                priority=draft.priority,
                status=LearningSignalStatus(draft.status),
                dedupe_key=draft.dedupe_key,
                available_at=draft.available_at,
                expires_at=draft.expires_at,
                payload=draft.payload,
            )
            session.add(signal)
            results.append(signal)
            continue

        existing.priority = draft.priority
        existing.payload = draft.payload
        existing.available_at = draft.available_at
        existing.expires_at = draft.expires_at
        if existing.status == LearningSignalStatus.snoozed and (
            existing.available_at is None or existing.available_at <= datetime.now(UTC)
        ):
            existing.status = LearningSignalStatus.active
        results.append(existing)

    if drafts:
        await session.commit()
    return results


async def list_active_learning_signals(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    study_space_ids: list[uuid.UUID] | None = None,
) -> list[LearningSignal]:
    now = datetime.now(UTC)
    statement = select(LearningSignal).where(
        LearningSignal.tenant_id == tenant_id,
        LearningSignal.user_id == user_id,
        LearningSignal.status == LearningSignalStatus.active,
        or_(LearningSignal.available_at.is_(None), LearningSignal.available_at <= now),
        or_(LearningSignal.expires_at.is_(None), LearningSignal.expires_at > now),
    )
    if study_space_ids is not None:
        statement = statement.where(LearningSignal.study_space_id.in_(study_space_ids))
    rows = await session.scalars(statement.order_by(LearningSignal.priority.desc(), LearningSignal.created_at.desc()))
    return list(rows)


async def set_learning_signal_status(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    signal_id: uuid.UUID,
    status: LearningSignalStatus,
    snooze_minutes: int | None = None,
) -> LearningSignal:
    signal = await session.scalar(
        select(LearningSignal).where(
            LearningSignal.id == signal_id,
            LearningSignal.tenant_id == tenant_id,
            LearningSignal.user_id == user_id,
        )
    )
    if signal is None:
        raise ValueError("Learning signal not found")

    signal.status = status
    signal.available_at = (
        datetime.now(UTC) + timedelta(minutes=snooze_minutes or 60)
        if status == LearningSignalStatus.snoozed
        else signal.available_at
    )
    signal.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(signal)
    return signal
