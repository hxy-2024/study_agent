import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_uploads
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


async def test_presign_upload_supplies_authorized_tenant_to_create_upload_request(
    monkeypatch,
) -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_create_upload_request(session, payload, **kwargs):
        captured["session"] = session
        captured["payload"] = payload
        captured["tenant_id"] = kwargs["tenant_id"]
        source_id = uuid.uuid4()
        return (
            SimpleNamespace(
                id=source_id,
                object_key=f"tenants/{kwargs['tenant_id']}/spaces/{payload.study_space_id}/sources/{source_id}/notes.pdf",
            ),
            "https://storage.example/upload",
        )

    monkeypatch.setattr(routes_uploads, "create_upload_request", fake_create_upload_request)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/uploads/presign",
                json={
                    "study_space_id": str(study_space_id),
                    "filename": "notes.pdf",
                    "content_type": "application/pdf",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["payload"].study_space_id == study_space_id
    assert "tenant_id" not in captured["payload"].model_fields_set
    assert response.json()["object_key"].startswith(f"tenants/{tenant_id}/")


async def test_presign_upload_rejects_request_body_tenant_id(monkeypatch) -> None:
    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_create_upload_request(session, payload, **kwargs):
        source_id = uuid.uuid4()
        tenant_id = getattr(payload, "tenant_id", kwargs.get("tenant_id"))
        return (
            SimpleNamespace(
                id=source_id,
                object_key=f"tenants/{tenant_id}/spaces/{payload.study_space_id}/sources/{source_id}/notes.pdf",
            ),
            "https://storage.example/upload",
        )

    monkeypatch.setattr(routes_uploads, "create_upload_request", fake_create_upload_request)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/uploads/presign",
                json={
                    "tenant_id": str(uuid.uuid4()),
                    "study_space_id": str(uuid.uuid4()),
                    "filename": "notes.pdf",
                    "content_type": "application/pdf",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_local_upload_put_stores_payload_without_auth(monkeypatch) -> None:
    source_id = uuid.uuid4()
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_store_local_upload(session, source_id, payload, content_type):
        captured["session"] = session
        captured["source_id"] = source_id
        captured["payload"] = payload
        captured["content_type"] = content_type

    monkeypatch.setattr(routes_uploads, "store_local_upload", fake_store_local_upload)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/uploads/local/{source_id}",
                content=b"# Local upload",
                headers={"Content-Type": "text/markdown"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert captured == {
        "session": captured["session"],
        "source_id": source_id,
        "payload": b"# Local upload",
        "content_type": "text/markdown",
    }
