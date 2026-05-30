import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_dashboard
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


async def test_dashboard_requires_auth_context() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard")

    assert response.status_code == 401


async def test_dashboard_uses_authorized_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    captured_kwargs = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_get_dashboard_summary(**kwargs):
        captured_kwargs.update(kwargs)
        return SimpleNamespace(
            spaces=[],
            pending_actions=[],
            supervision_refresh_count=0,
            recent_agent_runs=[],
        )

    monkeypatch.setattr(routes_dashboard, "get_dashboard_summary", fake_get_dashboard_summary)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["spaces"] == []
    assert captured_kwargs["tenant_id"] == tenant_id
    assert captured_kwargs["user_id"] == user_id


async def test_dashboard_recommendation_post_uses_authorized_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    captured_kwargs = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_get_main_agent_recommendation(**kwargs):
        captured_kwargs.update(kwargs)
        return SimpleNamespace(
            title="Review Retrieval",
            action_label="Review now",
            action_url="/chapters/chapter-1",
            recommendation_type="review_chapter",
            reason="Low mastery needs attention.",
            estimated_minutes=15,
            study_space_id=None,
            chapter_id=None,
            agent_type="main_agent",
            freshness="deterministic_fallback",
            strategy_version="main_agent_agenda_v2",
            source_signals={"mastery": 1},
            agent_run_id=None,
            secondary_actions=[],
        )

    monkeypatch.setattr(routes_dashboard, "get_main_agent_recommendation", fake_get_main_agent_recommendation)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/dashboard/recommendation",
                json={"available_minutes": 15, "intent": "review"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["recommendation_type"] == "review_chapter"
    assert captured_kwargs["tenant_id"] == tenant_id
    assert captured_kwargs["user_id"] == user_id
    assert captured_kwargs["request"].available_minutes == 15
    assert captured_kwargs["request"].intent == "review"
