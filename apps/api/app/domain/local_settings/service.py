import json
from pathlib import Path

import httpx

from app.domain.local_settings.schemas import (
    LocalAIModelsResponse,
    LocalAISettings,
    LocalAISettingsResponse,
    LocalAISettingsUpdate,
)


def load_local_ai_settings(*, path: str | Path) -> LocalAISettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return LocalAISettings()
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return LocalAISettings()
    return LocalAISettings.model_validate(payload)


def save_local_ai_settings(
    update: LocalAISettingsUpdate,
    *,
    path: str | Path,
) -> LocalAISettingsResponse:
    settings_path = Path(path)
    current = load_local_ai_settings(path=settings_path)
    update_payload = update.model_dump(exclude_unset=True)
    for secret_key in ("llm_api_key", "tavily_api_key"):
        if update_payload.get(secret_key) == "":
            update_payload.pop(secret_key)
    next_settings = current.model_copy(update={key: value for key, value in update_payload.items() if value is not None})
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(next_settings.model_dump(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return next_settings.to_response()


def _models_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/models"


def _extract_model_ids(payload: dict) -> list[str]:
    raw_models = payload.get("data")
    if not isinstance(raw_models, list):
        return []
    models: list[str] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id.strip():
            models.append(model_id.strip())
    return models


async def discover_local_ai_models(
    *,
    path: str | Path,
    client: httpx.AsyncClient,
) -> LocalAIModelsResponse:
    settings_path = Path(path)
    current = load_local_ai_settings(path=settings_path)
    response = await client.get(
        _models_url(current.llm_base_url),
        headers={"Authorization": f"Bearer {current.llm_api_key}"},
    )
    response.raise_for_status()
    models = _extract_model_ids(response.json())
    selected_model = models[0] if models else current.llm_model
    save_local_ai_settings(
        LocalAISettingsUpdate(
            llm_model=selected_model,
            available_models=models,
        ),
        path=settings_path,
    )
    return LocalAIModelsResponse(models=models, selected_model=selected_model)
