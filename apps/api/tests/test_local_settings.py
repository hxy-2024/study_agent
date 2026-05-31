from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.domain.chapter_mentor.providers import OpenAICompatibleAnswerProvider, create_answer_provider
from app.domain.local_settings.schemas import LocalAISettingsUpdate
from app.domain.local_settings.service import (
    discover_local_ai_models,
    load_local_ai_settings,
    save_local_ai_settings,
)


def test_local_ai_settings_roundtrip_masks_api_key(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"

    saved = save_local_ai_settings(
        LocalAISettingsUpdate(
            llm_provider="openai-compatible",
            llm_base_url="https://llm.example.test/v1",
            llm_model="study-model",
            llm_api_key="secret-key",
            embedding_base_url="https://dashscope.example.test/compatible-mode/v1",
            embedding_model="text-embedding-v4",
            embedding_api_key="embedding-secret",
            embedding_dimensions=1024,
            web_search_default_enabled=True,
            answer_style="socratic",
        ),
        path=path,
    )
    loaded = load_local_ai_settings(path=path)

    assert saved.llm_api_key == "secret-key"
    assert saved.llm_api_key_masked == "********"
    assert loaded.llm_provider == "openai-compatible"
    assert loaded.llm_api_key == "secret-key"
    assert loaded.embedding_model == "text-embedding-v4"
    assert loaded.embedding_api_key == "embedding-secret"
    assert loaded.embedding_dimensions == 1024
    assert loaded.to_response().llm_api_key == "secret-key"
    assert loaded.to_response().llm_api_key_masked == "********"
    assert loaded.to_response().embedding_api_key_masked == "********"
    assert loaded.to_response().answer_style == "socratic"


def test_local_ai_settings_roundtrip_locale_and_agent_prompts(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"

    save_local_ai_settings(
        LocalAISettingsUpdate(
            locale="zh-CN",
            main_agent_system_prompt="主 agent 负责规划今天先学什么。",
            session_tutor_system_prompt="二层 agent 监督学习会话。",
            chapter_mentor_system_prompt="三层 agent 协助章节问答。",
            answer_style="code_tutor",
        ),
        path=path,
    )
    loaded = load_local_ai_settings(path=path)

    assert loaded.locale == "zh-CN"
    assert loaded.main_agent_system_prompt == "主 agent 负责规划今天先学什么。"
    assert loaded.session_tutor_system_prompt == "二层 agent 监督学习会话。"
    assert loaded.chapter_mentor_system_prompt == "三层 agent 协助章节问答。"
    assert loaded.to_response().locale == "zh-CN"
    assert loaded.to_response().chapter_mentor_system_prompt == "三层 agent 协助章节问答。"


def test_local_ai_settings_preserves_existing_secret_when_update_sends_empty_string(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    save_local_ai_settings(
        LocalAISettingsUpdate(
            llm_api_key="secret-key",
            embedding_api_key="embedding-secret",
            embedding_dimensions=1024,
            tavily_api_key="tavily-secret",
        ),
        path=path,
    )

    save_local_ai_settings(
        LocalAISettingsUpdate(
            llm_model="new-model",
            llm_api_key="",
            embedding_api_key="",
            tavily_api_key="",
        ),
        path=path,
    )
    loaded = load_local_ai_settings(path=path)

    assert loaded.llm_model == "new-model"
    assert loaded.llm_api_key == "secret-key"
    assert loaded.embedding_api_key == "embedding-secret"
    assert loaded.tavily_api_key == "tavily-secret"


def test_local_ai_settings_can_clear_embedding_dimensions(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_local_ai_settings(
        LocalAISettingsUpdate(embedding_dimensions=1024),
        path=path,
    )

    save_local_ai_settings(
        LocalAISettingsUpdate(embedding_dimensions=None),
        path=path,
    )

    assert load_local_ai_settings(path=path).embedding_dimensions is None


@pytest.mark.anyio
async def test_discover_local_ai_models_uses_openai_compatible_models_endpoint(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    save_local_ai_settings(
        LocalAISettingsUpdate(
            llm_base_url="https://llm.example.test/v1",
            llm_api_key="secret-key",
        ),
        path=path,
    )
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "deepseek-chat"},
                    {"id": "deepseek-reasoner"},
                    {"id": ""},
                    {"name": "ignored"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await discover_local_ai_models(path=path, client=client)

    loaded = load_local_ai_settings(path=path)
    assert captured["url"] == "https://llm.example.test/v1/models"
    assert captured["authorization"] == "Bearer secret-key"
    assert response.models == ["deepseek-chat", "deepseek-reasoner"]
    assert response.selected_model == "deepseek-chat"
    assert loaded.llm_model == "deepseek-chat"
    assert loaded.available_models == ["deepseek-chat", "deepseek-reasoner"]


@pytest.mark.anyio
async def test_discover_local_embedding_models_filters_embedding_models(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_local_ai_settings(
        LocalAISettingsUpdate(
            embedding_base_url="https://dashscope.example.test/compatible-mode/v1",
            embedding_api_key="embedding-secret",
        ),
        path=path,
    )
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "deepseek-chat"},
                    {"id": "text-embedding-v4"},
                    {"id": "text-embedding-v3"},
                ]
            },
        )

    from app.domain.local_settings.service import discover_local_embedding_models

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await discover_local_embedding_models(path=path, client=client)

    loaded = load_local_ai_settings(path=path)
    assert captured["url"] == "https://dashscope.example.test/compatible-mode/v1/models"
    assert captured["authorization"] == "Bearer embedding-secret"
    assert response.models == ["text-embedding-v4", "text-embedding-v3"]
    assert response.selected_model == "text-embedding-v4"
    assert loaded.embedding_model == "text-embedding-v4"


@pytest.mark.anyio
async def test_discover_local_embedding_models_uses_dashscope_fallback_when_models_endpoint_fails(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    from app.domain.local_settings.service import discover_local_embedding_models

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await discover_local_embedding_models(
            path=path,
            client=client,
            update=LocalAISettingsUpdate(
                embedding_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                embedding_api_key="embedding-secret",
            ),
        )

    loaded = load_local_ai_settings(path=path)
    assert response.models[:2] == ["text-embedding-v4", "text-embedding-v3"]
    assert response.selected_model == "text-embedding-v4"
    assert loaded.embedding_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert loaded.embedding_model == "text-embedding-v4"


def test_create_answer_provider_uses_local_ai_settings_override(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_local_ai_settings(
        LocalAISettingsUpdate(
            llm_provider="openai-compatible",
            llm_base_url="https://llm.example.test/v1",
            llm_model="study-model",
            llm_api_key="secret-key",
        ),
        path=path,
    )

    provider = create_answer_provider(
        Settings(_env_file=None, llm_provider="deterministic", local_settings_path=str(path))
    )

    assert isinstance(provider, OpenAICompatibleAnswerProvider)
    assert provider.base_url == "https://llm.example.test/v1"
    assert provider.model == "study-model"


def test_create_answer_provider_treats_deepseek_as_openai_compatible(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_local_ai_settings(
        LocalAISettingsUpdate(
            llm_provider="deepseek",
            llm_base_url="https://api.deepseek.com",
            llm_model="deepseek-chat",
            llm_api_key="secret-key",
            answer_style="exam_review",
        ),
        path=path,
    )

    provider = create_answer_provider(
        Settings(_env_file=None, llm_provider="deterministic", local_settings_path=str(path))
    )

    assert isinstance(provider, OpenAICompatibleAnswerProvider)
    assert provider.base_url == "https://api.deepseek.com"
    assert provider.model == "deepseek-chat"
    assert provider.answer_style == "exam_review"
