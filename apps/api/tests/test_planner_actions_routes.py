import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_planner_actions
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


async def test_planner_actions_require_auth_context() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/study-spaces/{uuid.uuid4()}/planner-actions")

    assert response.status_code == 401


async def test_planner_actions_reject_client_supplied_tenant_scope() -> None:
    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/planner-actions/from-latest-state",
                json={
                    "tenant_id": str(uuid.uuid4()),
                    "study_space_id": str(uuid.uuid4()),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_list_actions_uses_authorized_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured_kwargs = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_list_planner_actions(**kwargs):
        captured_kwargs.update(kwargs)
        return SimpleNamespace(actions=[])

    monkeypatch.setattr(routes_planner_actions, "list_planner_actions", fake_list_planner_actions)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/study-spaces/{study_space_id}/planner-actions")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"actions": []}
    assert captured_kwargs["tenant_id"] == tenant_id
    assert captured_kwargs["user_id"] == user_id
    assert captured_kwargs["study_space_id"] == study_space_id


async def test_create_actions_uses_authorized_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured_kwargs = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_create_actions_from_latest_planner_state(**kwargs):
        captured_kwargs.update(kwargs)
        return SimpleNamespace(actions=[])

    monkeypatch.setattr(
        routes_planner_actions,
        "create_actions_from_latest_planner_state",
        fake_create_actions_from_latest_planner_state,
    )
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/planner-actions/from-latest-state",
                json={"study_space_id": str(study_space_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert captured_kwargs["tenant_id"] == tenant_id
    assert captured_kwargs["user_id"] == user_id
    assert captured_kwargs["study_space_id"] == study_space_id


async def test_update_action_uses_authorized_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    action_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured_kwargs = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_update_planner_action_status(**kwargs):
        captured_kwargs.update(kwargs)
        return SimpleNamespace(
            id=action_id,
            study_space_id=study_space_id,
            chapter_id=None,
            source_planner_state_id=None,
            action_type="review_chapter",
            status="accepted",
            title="Review",
            rationale="Reason",
            payload={},
            created_at=None,
            updated_at=None,
        )

    monkeypatch.setattr(routes_planner_actions, "update_planner_action_status", fake_update_planner_action_status)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/planner-actions/{action_id}/status", json={"status": "accepted"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured_kwargs["tenant_id"] == tenant_id
    assert captured_kwargs["user_id"] == user_id
    assert captured_kwargs["action_id"] == action_id
    assert captured_kwargs["status"] == "accepted"


async def test_update_action_maps_domain_error_to_400(monkeypatch) -> None:
    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_update_planner_action_status(**kwargs):
        raise ValueError("Unsupported planner action status")

    monkeypatch.setattr(routes_planner_actions, "update_planner_action_status", fake_update_planner_action_status)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/planner-actions/{uuid.uuid4()}/status", json={"status": "bad"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
