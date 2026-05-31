import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_ingestion
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.main import app


async def test_runtime_ingestion_uses_reader_factory_and_authorized_tenant(
    monkeypatch,
) -> None:
    source_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    job_id = uuid.UUID("00000000-0000-0000-0000-000000000003")
    session = object()
    reader = object()
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield session

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    def fake_create_runtime_text_source_reader() -> object:
        captured["reader_factory_called"] = True
        return reader

    async def fake_ingest_source(**kwargs) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            job_id=job_id,
            source_id=source_id,
            status="completed",
            chunk_count=2,
        )

    monkeypatch.setattr(
        routes_ingestion,
        "create_runtime_text_source_reader",
        fake_create_runtime_text_source_reader,
        raising=False,
    )
    monkeypatch.setattr(routes_ingestion, "ingest_source", fake_ingest_source)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/ingestion/sources/{source_id}/run")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["reader_factory_called"] is True
    assert captured["session"] is session
    assert captured["source_id"] == source_id
    assert captured["reader"] is reader
    assert isinstance(captured["embedding_provider"], DeterministicEmbeddingProvider)
    assert captured["tenant_id"] == tenant_id
    assert response.json() == {
        "job_id": str(job_id),
        "source_id": str(source_id),
        "status": "completed",
        "chunk_count": 2,
    }


async def test_runtime_ingestion_maps_value_error_to_400(monkeypatch) -> None:
    source_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    def fake_create_runtime_text_source_reader() -> object:
        return object()

    async def fake_ingest_source(**kwargs) -> None:
        raise ValueError("Source not found for tenant")

    monkeypatch.setattr(
        routes_ingestion,
        "create_runtime_text_source_reader",
        fake_create_runtime_text_source_reader,
        raising=False,
    )
    monkeypatch.setattr(routes_ingestion, "ingest_source", fake_ingest_source)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/ingestion/sources/{source_id}/run")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "Source not found for tenant"}


async def test_runtime_ingestion_maps_embedding_runtime_error_to_502(monkeypatch) -> None:
    source_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_ingest_source(**kwargs) -> None:
        raise RuntimeError("Embedding request failed: unauthorized")

    monkeypatch.setattr(routes_ingestion, "ingest_source", fake_ingest_source)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/ingestion/sources/{source_id}/run")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "Embedding request failed: unauthorized"}


async def test_runtime_ingestion_rejects_chat_model_embedding_preset(monkeypatch) -> None:
    source_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/ingestion/sources/{source_id}/run",
                json={"embedding_preset": "configured:deepseek-chat"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "not a retrieval embedding model" in response.json()["detail"]
