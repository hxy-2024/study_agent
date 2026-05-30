from pathlib import Path

from app.core.config import Settings
from app.domain.chapter_mentor.providers import OpenAICompatibleAnswerProvider, create_answer_provider
from app.domain.local_settings.schemas import LocalAISettingsUpdate
from app.domain.local_settings.service import load_local_ai_settings, save_local_ai_settings


def test_local_ai_settings_roundtrip_masks_api_key(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"

    saved = save_local_ai_settings(
        LocalAISettingsUpdate(
            llm_provider="openai-compatible",
            llm_base_url="https://llm.example.test/v1",
            llm_model="study-model",
            llm_api_key="secret-key",
            web_search_default_enabled=True,
            answer_style="socratic",
        ),
        path=path,
    )
    loaded = load_local_ai_settings(path=path)

    assert saved.llm_api_key_masked == "********"
    assert loaded.llm_provider == "openai-compatible"
    assert loaded.llm_api_key == "secret-key"
    assert loaded.to_response().llm_api_key_masked == "********"
    assert loaded.to_response().answer_style == "socratic"


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
