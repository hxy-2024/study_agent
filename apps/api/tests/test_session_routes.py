import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes_sessions
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.sessions.schemas import MessageResponse
from app.main import app


async def fake_db() -> AsyncGenerator[object, None]:
    yield object()


async def fake_context() -> CurrentUserContext:
    return CurrentUserContext(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    )


@pytest.mark.anyio
async def test_create_session_uses_authorized_tenant(monkeypatch) -> None:
    captured = {}
    chapter_id = uuid.uuid4()
    session_id = uuid.uuid4()

    async def fake_create_session_for_chapter(**kwargs):
        captured.update(kwargs)
        return type(
            "SessionRow",
            (),
            {
                "id": session_id,
                "study_space_id": uuid.uuid4(),
                "chapter_id": chapter_id,
                "title": "Intro session",
                "status": "active",
                "summary": None,
                "created_at": None,
                "updated_at": None,
            },
        )()

    monkeypatch.setattr(routes_sessions, "create_session_for_chapter", fake_create_session_for_chapter)
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/chapters/{chapter_id}/sessions",
                json={"title": "Intro session"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert captured["tenant_id"] == uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert captured["chapter_id"] == chapter_id


@pytest.mark.anyio
async def test_list_chapter_sessions_returns_sessions(monkeypatch) -> None:
    chapter_id = uuid.uuid4()

    async def fake_list_sessions_for_chapter(**kwargs):
        return [
            type(
                "SessionRow",
                (),
                {
                    "id": uuid.uuid4(),
                    "study_space_id": uuid.uuid4(),
                    "chapter_id": chapter_id,
                    "title": "Intro session",
                    "status": "active",
                    "summary": None,
                    "created_at": None,
                    "updated_at": None,
                },
            )()
        ]

    monkeypatch.setattr(routes_sessions, "list_sessions_for_chapter", fake_list_sessions_for_chapter)
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/chapters/{chapter_id}/sessions")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Intro session"


@pytest.mark.anyio
async def test_list_session_messages_uses_authorized_tenant(monkeypatch) -> None:
    captured = {}
    session_id = uuid.uuid4()

    async def fake_list_messages_for_session(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(routes_sessions, "list_messages_for_session", fake_list_messages_for_session)
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/sessions/{session_id}/messages")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["session_id"] == session_id
    assert captured["tenant_id"] == uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.anyio
async def test_session_tutor_message_rejects_client_tenant() -> None:
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/sessions/{uuid.uuid4()}/messages",
                json={"tenant_id": str(uuid.uuid4()), "content": "Explain this"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.anyio
async def test_create_session_message_uses_answer_service(monkeypatch) -> None:
    session_id = uuid.uuid4()
    captured = {}

    async def fake_answer_session_message(**kwargs):
        captured.update(kwargs)
        return MessageResponse(
            id=uuid.uuid4(),
            session_id=session_id,
            role="assistant",
            content="Answer",
            citations=[],
        )

    monkeypatch.setattr(routes_sessions, "answer_session_message", fake_answer_session_message)
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/sessions/{session_id}/messages",
                json={"content": "Explain"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["session_id"] == session_id
    assert captured["user_id"] == uuid.UUID("00000000-0000-0000-0000-000000000002")
    assert captured["content"] == "Explain"
