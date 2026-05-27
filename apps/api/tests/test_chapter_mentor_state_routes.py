import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes_chapter_mentor_state
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.chapter_mentor_state.schemas import ChapterMentorStateResponse
from app.main import app


TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


async def fake_db() -> AsyncGenerator[object, None]:
    yield object()


async def fake_context() -> CurrentUserContext:
    return CurrentUserContext(user_id=USER_ID, tenant_id=TENANT_ID)


@pytest.mark.anyio
async def test_run_chapter_summary_uses_authorized_tenant_and_chapter_id(monkeypatch) -> None:
    captured = {}
    chapter_id = uuid.uuid4()

    async def fake_generate_chapter_mentor_state(**kwargs):
        captured.update(kwargs)
        return ChapterMentorStateResponse(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            study_space_id=uuid.uuid4(),
            chapter_id=chapter_id,
            summary="Reviewed chapter discussion.",
            weak_points=[],
            next_actions=[],
            evidence=[],
            source_session_count=0,
            source_message_count=0,
        )

    monkeypatch.setattr(routes_chapter_mentor_state, "generate_chapter_mentor_state", fake_generate_chapter_mentor_state)
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agents/chapter-summary/run",
                json={"chapter_id": str(chapter_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == TENANT_ID
    assert captured["chapter_id"] == chapter_id


@pytest.mark.anyio
async def test_get_chapter_mentor_state_missing_returns_404(monkeypatch) -> None:
    async def fake_get_chapter_mentor_state(**kwargs):
        return None

    monkeypatch.setattr(routes_chapter_mentor_state, "get_chapter_mentor_state", fake_get_chapter_mentor_state)
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/chapters/{uuid.uuid4()}/mentor-state")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Chapter mentor state not found"


@pytest.mark.anyio
async def test_run_chapter_summary_rejects_client_supplied_tenant_id() -> None:
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agents/chapter-summary/run",
                json={
                    "tenant_id": str(uuid.uuid4()),
                    "chapter_id": str(uuid.uuid4()),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
