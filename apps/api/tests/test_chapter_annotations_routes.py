import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_chapter_annotations
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


async def fake_get_db_session() -> AsyncGenerator[object, None]:
    yield object()


def annotation_fixture(**overrides):
    values = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "study_space_id": uuid.uuid4(),
        "chapter_id": uuid.uuid4(),
        "source_chunk_id": None,
        "kind": "note",
        "content": "Remember the definition.",
        "quote": None,
        "anchor": {},
        "created_at": None,
        "updated_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


async def test_list_chapter_annotations_uses_authorized_tenant(monkeypatch) -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context():
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_list_chapter_annotations(**kwargs):
        captured.update(kwargs)
        return [annotation_fixture(tenant_id=tenant_id, user_id=user_id, chapter_id=chapter_id)]

    monkeypatch.setattr(routes_chapter_annotations, "list_chapter_annotations", fake_list_chapter_annotations)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/chapters/{chapter_id}/annotations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["chapter_id"] == chapter_id
    assert response.json()["annotations"][0]["content"] == "Remember the definition."


async def test_create_chapter_annotation_uses_authorized_user_context(monkeypatch) -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context():
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_create_chapter_annotation(**kwargs):
        captured.update(kwargs)
        return annotation_fixture(
            tenant_id=tenant_id,
            user_id=user_id,
            chapter_id=chapter_id,
            content=kwargs["payload"].content,
        )

    monkeypatch.setattr(routes_chapter_annotations, "create_chapter_annotation", fake_create_chapter_annotation)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/chapters/{chapter_id}/annotations",
                json={"kind": "note", "content": "Remember the definition."},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["user_id"] == user_id
    assert captured["chapter_id"] == chapter_id
    assert response.json()["annotation"]["kind"] == "note"


async def test_create_chapter_annotation_rejects_request_body_tenant_id() -> None:
    async def fake_context():
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/chapters/{uuid.uuid4()}/annotations",
                json={
                    "tenant_id": str(uuid.uuid4()),
                    "kind": "note",
                    "content": "No client tenant scope.",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_update_and_delete_annotation_use_authorized_tenant(monkeypatch) -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    annotation_id = uuid.uuid4()
    captured = {}

    async def fake_context():
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_update_chapter_annotation(**kwargs):
        captured["update"] = kwargs
        return annotation_fixture(id=annotation_id, tenant_id=tenant_id, user_id=user_id, content=kwargs["payload"].content)

    async def fake_delete_chapter_annotation(**kwargs):
        captured["delete"] = kwargs

    monkeypatch.setattr(routes_chapter_annotations, "update_chapter_annotation", fake_update_chapter_annotation)
    monkeypatch.setattr(routes_chapter_annotations, "delete_chapter_annotation", fake_delete_chapter_annotation)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            update_response = await client.patch(
                f"/api/v1/chapter-annotations/{annotation_id}",
                json={"content": "Updated note"},
            )
            delete_response = await client.delete(f"/api/v1/chapter-annotations/{annotation_id}")
    finally:
        app.dependency_overrides.clear()

    assert update_response.status_code == 200
    assert delete_response.status_code == 204
    assert captured["update"]["tenant_id"] == tenant_id
    assert captured["update"]["annotation_id"] == annotation_id
    assert captured["delete"]["tenant_id"] == tenant_id
    assert captured["delete"]["annotation_id"] == annotation_id
