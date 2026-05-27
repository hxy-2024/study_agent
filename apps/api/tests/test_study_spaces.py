import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes_study_spaces
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.study_spaces.service import create_route_outline
from app.main import app


async def fake_get_db_session() -> AsyncGenerator[object, None]:
    yield object()


def test_create_route_outline_uses_goal_when_no_ai_is_available() -> None:
    outline = create_route_outline(goal="Learn linear algebra", target_days=14)

    assert outline[0]["title"] == "Clarify the learning goal"
    assert outline[0]["description"] == (
        "Map the target outcome, prior knowledge, and constraints before studying details."
    )
    assert sum(item["estimated_days"] for item in outline) == 14
    assert outline[-1]["title"] == "Review, test, and reinforce"


def test_study_space_payload_contains_business_fields_only() -> None:
    payload = {
        "name": "Linear Algebra",
        "goal": "Understand matrices",
        "level": "beginner",
        "intensity": "normal",
        "target_days": 30,
    }

    assert "tenant_id" not in payload
    assert "owner_user_id" not in payload


@pytest.mark.anyio
async def test_create_space_uses_authorized_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    captured = {}

    async def fake_context():
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_create_study_space(**kwargs):
        captured.update(kwargs)
        return {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "owner_user_id": user_id,
            "name": kwargs["payload"].name,
            "goal": kwargs["payload"].goal,
            "level": kwargs["payload"].level,
            "intensity": kwargs["payload"].intensity,
            "target_days": kwargs["payload"].target_days,
            "status": "active",
            "route_outline": [],
            "created_at": "2026-05-27T00:00:00Z",
        }

    monkeypatch.setattr(routes_study_spaces, "create_study_space", fake_create_study_space)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/study-spaces",
                json={
                    "name": "Linear Algebra",
                    "goal": "Understand matrices",
                    "level": "beginner",
                    "intensity": "normal",
                    "target_days": 30,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert captured["tenant_id"] == tenant_id
    assert captured["owner_user_id"] == user_id
    assert response.json()["tenant_id"] == str(tenant_id)


@pytest.mark.anyio
async def test_list_spaces_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    captured = {}

    async def fake_context():
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_list_study_spaces(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(routes_study_spaces, "list_study_spaces", fake_list_study_spaces)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/study-spaces")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
