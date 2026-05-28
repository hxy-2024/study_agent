import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_space_planner
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


async def test_space_planner_run_requires_auth_context() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agents/space-planner/run",
            json={"study_space_id": str(uuid.uuid4())},
        )

    assert response.status_code == 401


async def test_space_planner_run_rejects_client_supplied_tenant_scope() -> None:
    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agents/space-planner/run",
                json={
                    "tenant_id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                    "study_space_id": str(uuid.uuid4()),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_space_planner_run_uses_authorized_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    state_id = uuid.uuid4()
    captured_kwargs = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_generate_space_planner_state(**kwargs):
        captured_kwargs.update(kwargs)
        return SimpleNamespace(
            id=state_id,
            study_space_id=study_space_id,
            summary="Plan ready",
            next_chapter_id=None,
            risk_chapters=[],
            review_recommendations=[],
            route_adjustments=[],
            evidence=[],
            updated_at=None,
        )

    monkeypatch.setattr(routes_space_planner, "generate_space_planner_state", fake_generate_space_planner_state)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agents/space-planner/run",
                json={"study_space_id": str(study_space_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["summary"] == "Plan ready"
    assert captured_kwargs["tenant_id"] == tenant_id
    assert captured_kwargs["user_id"] == user_id
    assert captured_kwargs["study_space_id"] == study_space_id


async def test_read_space_planner_state_returns_404_when_missing(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_get_space_planner_state(**kwargs):
        return None

    monkeypatch.setattr(routes_space_planner, "get_space_planner_state", fake_get_space_planner_state)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/study-spaces/{study_space_id}/planner-state")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
