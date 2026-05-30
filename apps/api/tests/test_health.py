from httpx import ASGITransport, AsyncClient

from app.api import routes_health
from app.main import app


async def test_health_returns_ok() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "study-agent-api"}


async def test_runtime_status_returns_local_dependency_checks(monkeypatch) -> None:
    async def fake_get_runtime_status() -> dict:
        return {
            "status": "degraded",
            "checks": [
                {"name": "api", "status": "ok", "detail": "API is responding."},
                {"name": "database", "status": "ok", "detail": "Database query succeeded."},
                {"name": "object_storage", "status": "error", "detail": "MinIO bucket is not reachable."},
                {"name": "llm", "status": "warning", "detail": "Deterministic local provider is active."},
            ],
        }

    monkeypatch.setattr(routes_health, "get_runtime_status", fake_get_runtime_status)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert [check["name"] for check in payload["checks"]] == ["api", "database", "object_storage", "llm"]
