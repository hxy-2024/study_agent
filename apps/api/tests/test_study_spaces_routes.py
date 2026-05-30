import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_study_spaces
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.models import StudySpaceStatus
from app.db.session import get_db_session
from app.main import app


async def fake_get_db_session() -> AsyncGenerator[object, None]:
    yield object()


async def test_delete_study_space_archives_space_for_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_archive_study_space(*, session, tenant_id, study_space_id):
        captured["session"] = session
        captured["tenant_id"] = tenant_id
        captured["study_space_id"] = study_space_id
        return SimpleNamespace(
            id=study_space_id,
            tenant_id=tenant_id,
            status=StudySpaceStatus.archived,
        )

    monkeypatch.setattr(routes_study_spaces, "archive_study_space", fake_archive_study_space)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(f"/api/v1/study-spaces/{study_space_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert captured["tenant_id"] == tenant_id
    assert captured["study_space_id"] == study_space_id


async def test_list_archived_spaces_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_list_archived_study_spaces(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(routes_study_spaces, "list_archived_study_spaces", fake_list_archived_study_spaces)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/study-spaces/archived")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id


async def test_restore_archived_space_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_restore_study_space(**kwargs):
        captured.update(kwargs)
        return {
            "id": study_space_id,
            "tenant_id": tenant_id,
            "owner_user_id": uuid.uuid4(),
            "name": "Archived space",
            "goal": "Restore it",
            "level": "beginner",
            "intensity": "normal",
            "target_days": 7,
            "status": "active",
            "route_outline": [],
            "created_at": "2026-05-27T00:00:00Z",
        }

    monkeypatch.setattr(routes_study_spaces, "restore_study_space", fake_restore_study_space)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/study-spaces/{study_space_id}/restore")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["study_space_id"] == study_space_id


async def test_export_space_supports_json_and_markdown(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_export_study_space(**kwargs):
        captured.update(kwargs)
        return {
            "study_space": {"id": str(study_space_id), "name": "RAG Basics", "goal": "Learn retrieval"},
            "sources": [{"filename": "notes.md", "status": "ready"}],
            "routes": [],
            "chapters": [{"title": "Chunking", "status": "completed"}],
            "sessions": [],
            "quizzes": [],
            "notes": [],
        }

    monkeypatch.setattr(routes_study_spaces, "export_study_space", fake_export_study_space)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            json_response = await client.get(f"/api/v1/study-spaces/{study_space_id}/export")
            markdown_response = await client.get(f"/api/v1/study-spaces/{study_space_id}/export?format=markdown")
    finally:
        app.dependency_overrides.clear()

    assert json_response.status_code == 200
    assert json_response.json()["study_space"]["name"] == "RAG Basics"
    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-type"].startswith("text/markdown")
    assert "# RAG Basics" in markdown_response.text
    assert "Chunking" in markdown_response.text
    assert captured["tenant_id"] == tenant_id


async def test_import_space_defaults_to_dry_run_and_uses_authorized_scope(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_import_study_space(**kwargs):
        captured.update(kwargs)
        return {
            "dry_run": True,
            "can_restore": False,
            "schema_version": 1,
            "original_study_space_id": "source-space",
            "summary": {"study_spaces": 1},
            "tenant_rewrite": {"to_tenant_id": str(tenant_id)},
            "user_rewrite": {"to_user_id": str(user_id)},
            "id_remap": {"study_spaces": {"source-space": "target-space"}},
            "warnings": [],
            "unsupported_write_models": ["sources"],
        }

    monkeypatch.setattr(routes_study_spaces, "import_study_space", fake_import_study_space)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/study-spaces/import", json={"payload": {"schema_version": 1}})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert captured["tenant_id"] == tenant_id
    assert captured["user_id"] == user_id
    assert captured["dry_run"] is True
    assert captured["payload"] == {"schema_version": 1}


async def test_import_space_non_dry_run_returns_501_until_restore_is_implemented(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_import_study_space(**kwargs):
        from app.domain.study_spaces.import_restore import StudySpaceImportNotImplementedError

        raise StudySpaceImportNotImplementedError("Study space import restore is not implemented")

    monkeypatch.setattr(routes_study_spaces, "import_study_space", fake_import_study_space)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/study-spaces/import",
                json={"dry_run": False, "payload": {"schema_version": 1}},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"]
