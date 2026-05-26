import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient

from app.api import routes_retrieval
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.rag.retrieval import RetrievedChunk
from app.main import app


async def test_retrieval_route_requires_auth_context() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/rag/retrieve",
            json={"study_space_id": str(uuid.uuid4()), "query": "linear algebra", "limit": 5},
        )

    assert response.status_code == 401


async def test_retrieval_route_supplies_authorized_tenant_to_retrieve_chunks(
    monkeypatch,
) -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured_kwargs = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_retrieve_chunks(**kwargs) -> list[RetrievedChunk]:
        captured_kwargs.update(kwargs)
        return []

    monkeypatch.setattr(routes_retrieval, "retrieve_chunks", fake_retrieve_chunks)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/rag/retrieve",
                json={
                    "study_space_id": str(study_space_id),
                    "query": "linear algebra",
                    "limit": 5,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"query": "linear algebra", "chunks": []}
    assert captured_kwargs["tenant_id"] == tenant_id
    assert captured_kwargs["study_space_id"] == study_space_id
    assert captured_kwargs["query"] == "linear algebra"
    assert captured_kwargs["limit"] == 5


async def test_retrieval_route_maps_domain_value_error_to_400(monkeypatch) -> None:
    tenant_id = uuid.uuid4()

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_retrieve_chunks(**kwargs) -> list[RetrievedChunk]:
        raise ValueError("Embedding dimension must be 16")

    monkeypatch.setattr(routes_retrieval, "retrieve_chunks", fake_retrieve_chunks)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/rag/retrieve",
                json={
                    "study_space_id": str(uuid.uuid4()),
                    "query": "linear algebra",
                    "limit": 5,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "Embedding dimension must be 16"}
