import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient

from app.api import routes_ingestion, routes_retrieval
from app.db.session import get_db_session
from app.main import app


def test_rag_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/api/v1/ingestion/sources/{source_id}/run" in paths
    assert "/api/v1/rag/retrieve" in paths


async def test_ingestion_route_returns_501_without_calling_ingest_source(monkeypatch) -> None:
    called = False

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_ingest_source(**kwargs) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(routes_ingestion, "ingest_source", fake_ingest_source)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/ingestion/sources/"
                "00000000-0000-0000-0000-000000000001/run"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 501
    assert response.json() == {
        "detail": "Runtime text reader is not configured for runtime ingestion"
    }
    assert called is False


async def test_retrieval_route_maps_domain_value_error_to_400(monkeypatch) -> None:
    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_retrieve_chunks(**kwargs) -> list:
        raise ValueError("Embedding dimension must be 16")

    monkeypatch.setattr(routes_retrieval, "retrieve_chunks", fake_retrieve_chunks)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/rag/retrieve",
                json={
                    "tenant_id": str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
                    "study_space_id": str(uuid.UUID("00000000-0000-0000-0000-000000000002")),
                    "query": "algebra",
                    "limit": 5,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "Embedding dimension must be 16"}
