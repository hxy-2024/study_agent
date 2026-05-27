import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_learning_routes
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


def fake_route(study_space_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000301"),
        study_space_id=study_space_id,
        version=1,
        status=SimpleNamespace(value="draft"),
        title="Route",
        summary="Summary",
        generation_strategy="deterministic",
        created_at=None,
        activated_at=None,
    )


def fake_chapter(route_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000401"),
        learning_route_id=route_id,
        order_index=1,
        title="Intro",
        goal="Learn basics",
        summary="Start here",
        estimated_days=3,
        status=SimpleNamespace(value="not_started"),
        source_chunk_refs=[],
    )


async def fake_get_db_session() -> AsyncGenerator[object, None]:
    yield object()


async def test_create_route_draft_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_create_route_draft(**kwargs):
        captured.update(kwargs)
        route = fake_route(study_space_id)
        return route, [fake_chapter(route.id)]

    monkeypatch.setattr(routes_learning_routes, "create_route_draft", fake_create_route_draft)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/study-spaces/{study_space_id}/route-drafts",
                json={"max_chapters": 4},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["route"]["status"] == "draft"
    assert captured["tenant_id"] == tenant_id
    assert captured["study_space_id"] == study_space_id
    assert captured["max_chapters"] == 4


async def test_create_route_draft_rejects_client_tenant_scope() -> None:
    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/study-spaces/{uuid.uuid4()}/route-drafts",
                json={"max_chapters": 4, "tenant_id": str(uuid.uuid4())},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_activate_route_maps_missing_route_to_404(monkeypatch) -> None:
    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_activate_route(**kwargs):
        raise ValueError("Route not found for tenant")

    monkeypatch.setattr(routes_learning_routes, "activate_route", fake_activate_route)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/routes/{uuid.uuid4()}/activate")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Route not found for tenant"}
