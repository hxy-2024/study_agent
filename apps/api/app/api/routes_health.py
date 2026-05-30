import asyncio
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.infrastructure.storage import create_s3_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "study-agent-api"}


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


async def _database_check() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
        return _check("database", "ok", "Database query succeeded.")
    except Exception as exc:
        return _check("database", "error", f"Database is not reachable: {exc}")


async def _object_storage_check() -> dict[str, str]:
    settings = get_settings()
    try:
        client = create_s3_client()
        await asyncio.to_thread(client.head_bucket, Bucket=settings.s3_bucket)
        return _check("object_storage", "ok", "MinIO bucket is reachable.")
    except Exception as exc:
        return _check("object_storage", "error", f"MinIO bucket is not reachable: {exc}")


def _llm_check() -> dict[str, str]:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    if provider == "deterministic":
        return _check("llm", "warning", "Deterministic local provider is active; no external LLM is configured.")
    if not settings.llm_api_key:
        return _check("llm", "warning", f"{settings.llm_provider} is selected but LLM_API_KEY is empty.")
    return _check("llm", "ok", f"{settings.llm_provider} provider is configured.")


async def get_runtime_status() -> dict[str, Any]:
    checks = [
        _check("api", "ok", "API is responding."),
        await _database_check(),
        await _object_storage_check(),
        _llm_check(),
    ]
    if any(check["status"] == "error" for check in checks):
        status = "degraded"
    elif any(check["status"] == "warning" for check in checks):
        status = "warning"
    else:
        status = "ok"
    return {"status": status, "checks": checks}


@router.get("/runtime/status")
async def runtime_status() -> dict[str, Any]:
    return await get_runtime_status()
