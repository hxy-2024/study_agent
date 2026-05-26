import uuid

import pytest
from fastapi import HTTPException

from app.core.auth import (
    CurrentUserContext,
    ensure_tenant_membership,
    get_current_user_context,
    parse_dev_auth_headers,
)
from app.core.config import Settings
from app.db.models import Membership


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


class FakeRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


@pytest.mark.anyio
async def test_get_current_user_context_uses_configured_header_names() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    request = FakeRequest(
        {
            "X-Dev-User": str(user_id),
            "X-Dev-Tenant": str(tenant_id),
        }
    )
    settings = Settings(
        _env_file=None,
        auth_user_header="X-Dev-User",
        auth_tenant_header="X-Dev-Tenant",
    )

    context = await get_current_user_context(request=request, settings=settings)

    assert context == CurrentUserContext(user_id=user_id, tenant_id=tenant_id)


@pytest.mark.anyio
async def test_get_current_user_context_fails_closed_when_dev_auth_disabled() -> None:
    request = FakeRequest(
        {
            "X-User-Id": str(uuid.uuid4()),
            "X-Tenant-Id": str(uuid.uuid4()),
        }
    )
    settings = Settings(_env_file=None, dev_auth_enabled=False)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_context(request=request, settings=settings)

    assert exc_info.value.status_code == 501
    assert exc_info.value.detail == "Production auth provider is not configured"


class FakeScalarSession:
    def __init__(self, result):
        self.result = result

    async def scalar(self, statement):
        self.statement = statement
        return self.result


@pytest.mark.anyio
async def test_ensure_tenant_membership_allows_existing_membership() -> None:
    context = CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())
    membership = Membership(tenant_id=context.tenant_id, user_id=context.user_id, role="owner")
    session = FakeScalarSession(result=membership)

    result = await ensure_tenant_membership(context=context, session=session)

    assert result == context


@pytest.mark.anyio
async def test_ensure_tenant_membership_rejects_missing_membership() -> None:
    context = CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())
    session = FakeScalarSession(result=None)

    with pytest.raises(HTTPException) as exc_info:
        await ensure_tenant_membership(context=context, session=session)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User is not a member of this tenant"
