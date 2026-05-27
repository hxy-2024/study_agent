import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes_chapter_study
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.chapter_study.schemas import (
    ChapterStudyChapterResponse,
    ChapterStudyDetailResponse,
    ChapterStudyRouteResponse,
    ChapterStudySpaceResponse,
)
from app.main import app


async def fake_get_db_session() -> AsyncGenerator[object, None]:
    yield object()


def detail_fixture(chapter_id: uuid.UUID) -> ChapterStudyDetailResponse:
    study_space_id = uuid.uuid4()
    route_id = uuid.uuid4()
    return ChapterStudyDetailResponse(
        chapter=ChapterStudyChapterResponse(
            id=chapter_id,
            study_space_id=study_space_id,
            learning_route_id=route_id,
            order_index=1,
            title="Intro",
            goal="Learn basics",
            summary="Start here",
            estimated_days=3,
            status="active",
            source_chunk_refs=[],
        ),
        route=ChapterStudyRouteResponse(
            id=route_id,
            study_space_id=study_space_id,
            version=1,
            status="active",
            title="Route",
        ),
        study_space=ChapterStudySpaceResponse(id=study_space_id, name="Linear Algebra"),
        evidence=[],
        next_chapter_id=None,
    )


@pytest.mark.anyio
async def test_get_chapter_detail_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context():
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_get_chapter_detail(**kwargs):
        captured.update(kwargs)
        return detail_fixture(chapter_id)

    monkeypatch.setattr(routes_chapter_study, "get_chapter_detail", fake_get_chapter_detail)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/chapters/{chapter_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["chapter_id"] == chapter_id
    assert response.json()["chapter"]["title"] == "Intro"


@pytest.mark.anyio
async def test_complete_chapter_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context():
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_complete_chapter(**kwargs):
        captured.update(kwargs)
        return detail_fixture(chapter_id)

    monkeypatch.setattr(routes_chapter_study, "complete_chapter", fake_complete_chapter)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/chapters/{chapter_id}/complete")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["chapter_id"] == chapter_id


@pytest.mark.anyio
async def test_chapter_not_found_maps_to_404(monkeypatch) -> None:
    chapter_id = uuid.uuid4()

    async def fake_context():
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_get_chapter_detail(**kwargs):
        raise ValueError("Chapter not found for tenant")

    monkeypatch.setattr(routes_chapter_study, "get_chapter_detail", fake_get_chapter_detail)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/chapters/{chapter_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
