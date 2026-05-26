from app.core.config import Settings


def test_dev_auth_settings_default_to_enabled_for_local_foundation() -> None:
    settings = Settings()

    assert settings.dev_auth_enabled is True
    assert settings.auth_user_header == "X-User-Id"
    assert settings.auth_tenant_header == "X-Tenant-Id"
