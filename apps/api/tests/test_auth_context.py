import uuid

import pytest
from fastapi import HTTPException

from app.core.auth import CurrentUserContext, parse_dev_auth_headers
from app.core.config import Settings


def test_dev_auth_settings_default_to_enabled_for_local_foundation(monkeypatch) -> None:
    monkeypatch.delenv("DEV_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("AUTH_USER_HEADER", raising=False)
    monkeypatch.delenv("AUTH_TENANT_HEADER", raising=False)

    settings = Settings(_env_file=None)

    assert settings.dev_auth_enabled is True
    assert settings.auth_user_header == "X-User-Id"
    assert settings.auth_tenant_header == "X-Tenant-Id"


def test_parse_dev_auth_headers_returns_context() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    context = parse_dev_auth_headers(
        user_id_header=str(user_id),
        tenant_id_header=str(tenant_id),
    )

    assert context == CurrentUserContext(user_id=user_id, tenant_id=tenant_id)


def test_parse_dev_auth_headers_requires_both_headers() -> None:
    with pytest.raises(HTTPException) as exc_info:
        parse_dev_auth_headers(user_id_header=None, tenant_id_header=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing development auth headers"


def test_parse_dev_auth_headers_rejects_invalid_uuid() -> None:
    with pytest.raises(HTTPException) as exc_info:
        parse_dev_auth_headers(user_id_header="not-a-uuid", tenant_id_header=str(uuid.uuid4()))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid development auth header UUID"
