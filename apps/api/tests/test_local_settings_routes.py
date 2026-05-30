import uuid

from httpx import ASGITransport, AsyncClient

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
                    "web_search_default_enabled": True,
                    "answer_style": "exam_review",
                },
            )
            read = await client.get("/api/v1/local-settings/ai")
    finally:
        app.dependency_overrides.clear()

    assert update.status_code == 200
    assert update.json()["llm_api_key_masked"] == "********"
    assert read.status_code == 200
    assert read.json()["llm_model"] == "study-model"
    assert read.json()["llm_api_key_masked"] == "********"
    assert read.json()["answer_style"] == "exam_review"
