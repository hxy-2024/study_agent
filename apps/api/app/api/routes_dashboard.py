from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.dashboard.schemas import DashboardRecommendation, DashboardRecommendationRequest, DashboardResponse
from app.domain.dashboard.service import get_dashboard_summary, get_main_agent_recommendation

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
async def read_dashboard(
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardResponse:
    return await get_dashboard_summary(
        session=session,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
    )


@router.post("/dashboard/recommendation", response_model=DashboardRecommendation)
async def recommend_dashboard_next_action(
    request: DashboardRecommendationRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardRecommendation:
    return await get_main_agent_recommendation(
        session=session,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        request=request,
    )
