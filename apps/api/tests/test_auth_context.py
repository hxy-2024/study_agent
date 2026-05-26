from app.core.config import Settings


def test_dev_auth_settings_default_to_enabled_for_local_foundation(monkeypatch) -> None:
    monkeypatch.delenv("DEV_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("AUTH_USER_HEADER", raising=False)
    monkeypatch.delenv("AUTH_TENANT_HEADER", raising=False)

    settings = Settings(_env_file=None)

    assert settings.dev_auth_enabled is True
    assert settings.auth_user_header == "X-User-Id"
    assert settings.auth_tenant_header == "X-Tenant-Id"
