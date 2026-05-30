import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.review_queue.schemas import ReviewQueueResponse
from app.domain.review_queue.service import get_review_queue

router = APIRouter(tags=["review-queue"])


@router.get("/review-queue", response_model=ReviewQueueResponse)
async def read_review_queue(
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ReviewQueueResponse:
    items = await get_review_queue(
        session=session,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
    )
    return ReviewQueueResponse(items=items)


@router.get("/study-spaces/{study_space_id}/review-queue", response_model=ReviewQueueResponse)
async def read_study_space_review_queue(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ReviewQueueResponse:
    items = await get_review_queue(
        session=session,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        study_space_id=study_space_id,
    )
    return ReviewQueueResponse(items=items)
