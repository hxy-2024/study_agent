import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient

from app.api import routes_uploads
from app.db.session import get_db_session
from app.main import app


async def test_local_upload_route_stores_payload_without_auth(monkeypatch) -> None:
    source_id = uuid.uuid4()
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_store_local_upload(session, source_id, payload, content_type):
        captured["session"] = session
        captured["source_id"] = source_id
        captured["payload"] = payload
        captured["content_type"] = content_type

    monkeypatch.setattr(routes_uploads, "store_local_upload", fake_store_local_upload)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/uploads/local/{source_id}",
                content=b"# Local source",
                headers={"content-type": "text/markdown"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert captured == {
        "session": captured["session"],
        "source_id": source_id,
        "payload": b"# Local source",
        "content_type": "text/markdown",
    }
