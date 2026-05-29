import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes_sources
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.models import SourceStatus
from app.db.session import get_db_session
from app.domain.sources.schemas import TextSourceCreateRequest
from app.domain.sources.service import create_text_source
from app.main import app


async def test_create_text_source_writes_text_and_marks_uploaded(monkeypatch) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    study_space_id = uuid.UUID("00000000-0000-0000-0000-000000000101")
    payload = TextSourceCreateRequest(
        study_space_id=study_space_id,
        filename="pasted notes.md",
        content_type="text/markdown",
        content="# Notes\nImportant point.",
    )
    writes: list[tuple[str, str, str]] = []

    class FakeWriter:
        async def write_text(self, object_key: str, content: str, content_type: str) -> None:
            writes.append((object_key, content, content_type))

    class FakeSession:
        def add(self, source):
            self.source = source

        async def commit(self):
            self.committed = True

        async def refresh(self, source):
            source.id = uuid.uuid4()

        async def scalar(self, statement):
            return SimpleNamespace(id=study_space_id)

    session = FakeSession()
    source = await create_text_source(
        session,
        payload,
        tenant_id=tenant_id,
        writer=FakeWriter(),
    )

    assert source is session.source
    assert source.tenant_id == tenant_id
    assert source.study_space_id == study_space_id
    assert source.status == SourceStatus.uploaded
    assert source.object_key.startswith(f"tenants/{tenant_id}/spaces/{study_space_id}/sources/")
    assert source.object_key.endswith("/pasted-notes.md")
    assert writes == [(source.object_key, "# Notes\nImportant point.", "text/markdown")]


async def test_create_text_source_rejects_binary_content_type() -> None:
    payload = TextSourceCreateRequest(
        study_space_id=uuid.uuid4(),
        filename="notes.pdf",
        content_type="application/pdf",
        content="not text",
    )

    with pytest.raises(ValueError, match="Pasted sources support only text"):
        await create_text_source(
            SimpleNamespace(),
            payload,
            tenant_id=uuid.uuid4(),
            writer=SimpleNamespace(),
        )


async def test_create_text_source_route_uses_authorized_tenant(monkeypatch) -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    source_id = uuid.uuid4()
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_create_text_source(session, payload, **kwargs):
        captured["session"] = session
        captured["payload"] = payload
        captured["tenant_id"] = kwargs["tenant_id"]
        captured["writer"] = kwargs["writer"]
        return SimpleNamespace(
            id=source_id,
            tenant_id=kwargs["tenant_id"],
            study_space_id=payload.study_space_id,
            filename=payload.filename,
            content_type=payload.content_type,
            object_key=f"tenants/{kwargs['tenant_id']}/spaces/{payload.study_space_id}/sources/{source_id}/notes.md",
            status=SourceStatus.uploaded,
            error_message=None,
            created_at=None,
        )

    monkeypatch.setattr(routes_sources, "create_text_source", fake_create_text_source)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sources/from-text",
                json={
                    "study_space_id": str(study_space_id),
                    "filename": "notes.md",
                    "content_type": "text/markdown",
                    "content": "# Notes",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["payload"].study_space_id == study_space_id
    assert response.json()["source"]["status"] == "uploaded"


async def test_create_text_source_route_rejects_body_tenant_id(monkeypatch) -> None:
    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sources/from-text",
                json={
                    "tenant_id": str(uuid.uuid4()),
                    "study_space_id": str(uuid.uuid4()),
                    "filename": "notes.md",
                    "content_type": "text/markdown",
                    "content": "# Notes",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
