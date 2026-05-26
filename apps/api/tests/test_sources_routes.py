import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_sources
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.models import SourceStatus
from app.db.session import get_db_session
from app.main import app


async def test_list_sources_supplies_authorized_tenant_to_service(monkeypatch) -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    source_id = uuid.uuid4()
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_list_sources_for_space(session, space_id, tenant):
        captured["session"] = session
        captured["study_space_id"] = space_id
        captured["tenant_id"] = tenant
        return [
            SimpleNamespace(
                id=source_id,
                study_space_id=study_space_id,
                filename="notes.pdf",
                content_type="application/pdf",
                object_key=f"tenants/{tenant_id}/spaces/{study_space_id}/sources/{source_id}/notes.pdf",
                status=SourceStatus.pending_upload,
                error_message=None,
                created_at=created_at,
            )
        ]

    monkeypatch.setattr(routes_sources, "list_sources_for_space", fake_list_sources_for_space)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/study-spaces/{study_space_id}/sources")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["study_space_id"] == study_space_id
    assert response.json() == {
        "sources": [
            {
                "id": str(source_id),
                "study_space_id": str(study_space_id),
                "filename": "notes.pdf",
                "content_type": "application/pdf",
                "object_key": f"tenants/{tenant_id}/spaces/{study_space_id}/sources/{source_id}/notes.pdf",
                "status": "pending_upload",
                "error_message": None,
                "created_at": "2026-01-02T03:04:05Z",
            }
        ]
    }


async def test_mark_source_uploaded_maps_missing_source_to_404(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_mark_source_uploaded(session, requested_source_id, requested_tenant_id):
        assert requested_source_id == source_id
        assert requested_tenant_id == tenant_id
        raise ValueError("Source not found for tenant")

    monkeypatch.setattr(routes_sources, "mark_source_uploaded", fake_mark_source_uploaded)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/sources/{source_id}/uploaded")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Source not found for tenant"}
