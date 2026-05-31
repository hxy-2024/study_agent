import json
from pathlib import Path

import httpx

from app.domain.local_settings.schemas import (
    LocalEmbeddingModelsResponse,
    LocalAIModelsResponse,
    LocalAISettings,
    LocalAISettingsResponse,
    LocalAISettingsUpdate,
)
from app.domain.rag.embeddings import is_likely_embedding_model

DASHSCOPE_EMBEDDING_MODELS = [
    "text-embedding-v4",
    "text-embedding-v3",
    "text-embedding-v2",
    "text-embedding-v1",
]


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
    for secret_key in ("llm_api_key", "embedding_api_key", "tavily_api_key"):
        if update_payload.get(secret_key) == "":
            update_payload.pop(secret_key)
    nullable_update_keys = {"embedding_dimensions"}
    next_settings = current.model_copy(
        update={
            key: value
            for key, value in update_payload.items()
            if value is not None or key in nullable_update_keys
        }
    )
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


async def discover_local_embedding_models(
    *,
    path: str | Path,
    client: httpx.AsyncClient,
    update: LocalAISettingsUpdate | None = None,
) -> LocalEmbeddingModelsResponse:
    settings_path = Path(path)
    if update is not None:
        save_local_ai_settings(update, path=settings_path)
    current = load_local_ai_settings(path=settings_path)
    base_url = current.embedding_base_url or current.llm_base_url
    api_key = current.embedding_api_key or current.llm_api_key
    models: list[str] = []
    try:
        response = await client.get(
            _models_url(base_url),
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        models = [model for model in _extract_model_ids(response.json()) if is_likely_embedding_model(model)]
    except httpx.HTTPError:
        if "dashscope.aliyuncs.com" not in base_url:
            raise
    if not models and "dashscope.aliyuncs.com" in base_url:
        models = DASHSCOPE_EMBEDDING_MODELS
    selected_model = current.embedding_model if current.embedding_model in models else (models[0] if models else "")
    if selected_model:
        save_local_ai_settings(
            LocalAISettingsUpdate(embedding_model=selected_model),
            path=settings_path,
        )
    return LocalEmbeddingModelsResponse(models=models, selected_model=selected_model)
