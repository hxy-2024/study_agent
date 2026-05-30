import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient

from app.api import routes_review_queue
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app
from app.domain.review_queue.schemas import ReviewQueueItem


async def test_review_queue_route_uses_authorized_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    captured_kwargs = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_get_review_queue(**kwargs):
        captured_kwargs.update(kwargs)
        return [
            ReviewQueueItem(
                id="review:chapter-1:mastery",
                kind="review_chapter",
                study_space_id=uuid.uuid4(),
                chapter_id=uuid.uuid4(),
                quiz_id=None,
                title="Review Retrieval",
                reason="Low mastery.",
                priority=90,
                estimated_minutes=20,
                action_url="/chapters/chapter-1",
                source_signals={"review_candidates": 1},
            )
        ]

    monkeypatch.setattr(routes_review_queue, "get_review_queue", fake_get_review_queue)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/review-queue")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["kind"] == "review_chapter"
    assert captured_kwargs["tenant_id"] == tenant_id
    assert captured_kwargs["user_id"] == user_id
