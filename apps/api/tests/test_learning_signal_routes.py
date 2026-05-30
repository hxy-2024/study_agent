import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_learning_signals
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.models import LearningSignalStatus
from app.db.session import get_db_session
from app.main import app


async def test_dismiss_learning_signal_route_uses_authorized_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    signal_id = uuid.uuid4()
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_set_learning_signal_status(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id=signal_id,
            tenant_id=tenant_id,
            user_id=user_id,
            study_space_id=uuid.uuid4(),
            chapter_id=None,
            quiz_id=None,
            agent_type=SimpleNamespace(value="review_planner"),
            signal_type="review_chapter",
            priority=80,
            status=LearningSignalStatus.dismissed,
            dedupe_key="review:chapter:mastery",
            available_at=None,
            expires_at=None,
            payload={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    monkeypatch.setattr(routes_learning_signals, "set_learning_signal_status", fake_set_learning_signal_status)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/learning-signals/{signal_id}/dismiss")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"
    assert captured["tenant_id"] == tenant_id
    assert captured["user_id"] == user_id
    assert captured["signal_id"] == signal_id
