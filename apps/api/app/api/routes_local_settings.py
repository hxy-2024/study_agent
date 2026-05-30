from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.core.config import Settings, get_settings
from app.domain.local_settings.schemas import LocalAISettingsResponse, LocalAISettingsUpdate
from app.domain.local_settings.service import load_local_ai_settings, save_local_ai_settings

router = APIRouter(tags=["local-settings"])


@router.get("/local-settings/ai", response_model=LocalAISettingsResponse)
async def read_local_ai_settings(
    _context: CurrentUserContext = Depends(get_authorized_user_context),
    settings: Settings = Depends(get_settings),
) -> LocalAISettingsResponse:
    return load_local_ai_settings(path=settings.local_settings_path).to_response()


@router.put("/local-settings/ai", response_model=LocalAISettingsResponse)
async def update_local_ai_settings(
    payload: LocalAISettingsUpdate,
    _context: CurrentUserContext = Depends(get_authorized_user_context),
    settings: Settings = Depends(get_settings),
) -> LocalAISettingsResponse:
    return save_local_ai_settings(payload, path=settings.local_settings_path)
