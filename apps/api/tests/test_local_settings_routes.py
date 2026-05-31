import uuid

import httpx
from httpx import ASGITransport, AsyncClient

from app.api import routes_local_settings
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.core.config import Settings, get_settings
from app.main import app


async def test_local_ai_settings_route_roundtrip_masks_api_key(tmp_path) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    def fake_get_settings() -> Settings:
        return Settings(_env_file=None, local_settings_path=str(tmp_path / "settings.json"))

    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    app.dependency_overrides[get_settings] = fake_get_settings
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            update = await client.put(
                "/api/v1/local-settings/ai",
                json={
                    "llm_provider": "openai-compatible",
                    "llm_base_url": "https://llm.example.test/v1",
                    "llm_model": "study-model",
                    "llm_api_key": "secret-key",
                    "embedding_base_url": "https://dashscope.example.test/compatible-mode/v1",
                    "embedding_model": "text-embedding-v4",
                    "embedding_api_key": "embedding-secret",
                    "embedding_dimensions": 1024,
                    "web_search_default_enabled": True,
                    "answer_style": "exam_review",
                },
            )
            read = await client.get("/api/v1/local-settings/ai")
    finally:
        app.dependency_overrides.clear()

    assert update.status_code == 200
    assert update.json()["llm_api_key_masked"] == "********"
    assert update.json()["embedding_api_key_masked"] == "********"
    assert read.status_code == 200
    assert read.json()["llm_model"] == "study-model"
    assert read.json()["embedding_model"] == "text-embedding-v4"
    assert read.json()["embedding_dimensions"] == 1024
    assert read.json()["llm_api_key_masked"] == "********"
    assert read.json()["answer_style"] == "exam_review"


async def test_local_ai_models_route_discovers_and_persists_models(tmp_path, monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    settings_path = tmp_path / "settings.json"

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    def fake_get_settings() -> Settings:
        return Settings(_env_file=None, local_settings_path=str(settings_path))

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def get(self, url, *, headers):
            assert url == "https://llm.example.test/v1/models"
            assert headers["Authorization"] == "Bearer secret-key"
            return httpx.Response(
                200,
                json={"data": [{"id": "deepseek-chat"}, {"id": "deepseek-reasoner"}]},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(routes_local_settings.httpx, "AsyncClient", FakeAsyncClient)
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    app.dependency_overrides[get_settings] = fake_get_settings
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put(
                "/api/v1/local-settings/ai",
                json={
                    "llm_base_url": "https://llm.example.test/v1",
                    "llm_api_key": "secret-key",
                    "llm_model": "old-model",
                },
            )
            response = await client.post("/api/v1/local-settings/ai/models")
            read = await client.get("/api/v1/local-settings/ai")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["models"] == ["deepseek-chat", "deepseek-reasoner"]
    assert response.json()["selected_model"] == "deepseek-chat"
    assert read.json()["available_models"] == ["deepseek-chat", "deepseek-reasoner"]
    assert read.json()["llm_model"] == "deepseek-chat"
