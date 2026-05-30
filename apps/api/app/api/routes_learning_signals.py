import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.models import LearningSignalStatus
from app.db.session import get_db_session
from app.domain.learning_signals.schemas import LearningSignalResponse, LearningSignalSnoozeRequest
from app.domain.learning_signals.service import build_learning_signal_response, set_learning_signal_status

router = APIRouter(prefix="/learning-signals", tags=["learning-signals"])


async def _update_status(
    *,
    signal_id: uuid.UUID,
    status: LearningSignalStatus,
    context: CurrentUserContext,
    session: AsyncSession,
    snooze_minutes: int | None = None,
) -> LearningSignalResponse:
    try:
        signal = await set_learning_signal_status(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            signal_id=signal_id,
            status=status,
            snooze_minutes=snooze_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return build_learning_signal_response(signal)


@router.post("/{signal_id}/complete", response_model=LearningSignalResponse)
async def complete_learning_signal(
    signal_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> LearningSignalResponse:
    return await _update_status(
        signal_id=signal_id,
        status=LearningSignalStatus.completed,
        context=context,
        session=session,
    )


@router.post("/{signal_id}/dismiss", response_model=LearningSignalResponse)
async def dismiss_learning_signal(
    signal_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> LearningSignalResponse:
    return await _update_status(
        signal_id=signal_id,
        status=LearningSignalStatus.dismissed,
        context=context,
        session=session,
    )


@router.post("/{signal_id}/snooze", response_model=LearningSignalResponse)
async def snooze_learning_signal(
    signal_id: uuid.UUID,
    payload: LearningSignalSnoozeRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> LearningSignalResponse:
    return await _update_status(
        signal_id=signal_id,
        status=LearningSignalStatus.snoozed,
        context=context,
        session=session,
        snooze_minutes=payload.minutes,
    )
