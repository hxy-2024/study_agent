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
