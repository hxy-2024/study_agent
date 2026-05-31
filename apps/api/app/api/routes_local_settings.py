import httpx
from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.core.config import Settings, get_settings
from app.domain.local_settings.schemas import (
    LocalEmbeddingModelsResponse,
    LocalAIModelsResponse,
    LocalAISettingsResponse,
    LocalAISettingsUpdate,
)
from app.domain.local_settings.service import (
    discover_local_embedding_models,
    discover_local_ai_models,
    load_local_ai_settings,
    save_local_ai_settings,
)

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


@router.post("/local-settings/ai/models", response_model=LocalAIModelsResponse)
async def refresh_local_ai_models(
    _context: CurrentUserContext = Depends(get_authorized_user_context),
    settings: Settings = Depends(get_settings),
) -> LocalAIModelsResponse:
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        return await discover_local_ai_models(path=settings.local_settings_path, client=client)


@router.post("/local-settings/ai/embedding-models", response_model=LocalEmbeddingModelsResponse)
async def refresh_local_embedding_models(
    payload: LocalAISettingsUpdate | None = None,
    _context: CurrentUserContext = Depends(get_authorized_user_context),
    settings: Settings = Depends(get_settings),
) -> LocalEmbeddingModelsResponse:
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        return await discover_local_embedding_models(
            path=settings.local_settings_path,
            client=client,
            update=payload,
        )
