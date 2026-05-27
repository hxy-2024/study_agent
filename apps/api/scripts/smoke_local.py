import argparse
import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000002"
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
SMOKE_MARKDOWN = b"# RAG fundamentals\n\nRAG retrieves evidence before answering.\n"


class SmokeHttp(Protocol):
    async def get(self, path: str) -> dict[str, Any]:
        """Send a GET request to the API base URL."""

    async def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a POST request to the API base URL."""

    async def put_bytes(self, url: str, content: bytes, content_type: str) -> None:
        """Upload raw bytes to a presigned URL."""


class HttpxSmokeHttp:
    def __init__(self, api_base_url: str, user_id: str, tenant_id: str, timeout: float = 30.0) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.headers = {
            "X-User-Id": user_id,
            "X-Tenant-Id": tenant_id,
        }
        self.timeout = timeout

    async def get(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.api_base_url}{path}", headers=self.headers)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base_url}{path}",
                headers=self.headers,
                json=json,
            )
        response.raise_for_status()
        return response.json()

    async def put_bytes(self, url: str, content: bytes, content_type: str) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(
                url,
                content=content,
                headers={"Content-Type": content_type},
            )
        response.raise_for_status()


@dataclass(frozen=True)
class SmokeClient:
    api_base_url: str
    user_id: str
    tenant_id: str
    http: SmokeHttp | None = None

    def api(self) -> SmokeHttp:
        if self.http is not None:
            return self.http
        return HttpxSmokeHttp(
            api_base_url=self.api_base_url,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
        )


async def run_smoke(client: SmokeClient) -> dict[str, Any]:
    http = client.api()
    health = await http.get("/health")

    space = await http.post(
        "/study-spaces",
        {
            "name": "Local smoke study space",
            "goal": "Understand retrieval augmented generation fundamentals.",
            "level": "beginner",
            "intensity": "normal",
            "target_days": 7,
        },
    )
    space_id = space["id"]

    presign = await http.post(
        "/uploads/presign",
        {
            "study_space_id": space_id,
            "filename": "local-smoke.md",
            "content_type": "text/markdown",
        },
    )
    source_id = presign["source_id"]
    await http.put_bytes(presign["upload_url"], SMOKE_MARKDOWN, "text/markdown")

    await http.post(f"/sources/{source_id}/uploaded")
    ingestion = await http.post(f"/ingestion/sources/{source_id}/run")
    chunks = await http.get(f"/sources/{source_id}/chunks")
    route = await http.post(f"/study-spaces/{space_id}/route-drafts", {"max_chapters": 3})
    chapter_id = route["chapters"][0]["id"]
    mentor = await http.post(
        f"/chapters/{chapter_id}/mentor/questions",
        {"question": "What should I focus on first?"},
    )
    completed = await http.post(f"/chapters/{chapter_id}/complete")

    return {
        "health": health["status"],
        "space_id": space_id,
        "source_id": source_id,
        "chunk_count": len(chunks["chunks"]),
        "ingestion_status": ingestion["status"],
        "chapter_id": chapter_id,
        "mentor_citation_count": len(mentor["citations"]),
        "chapter_status": completed["chapter"]["status"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local API smoke flow.")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await run_smoke(
        SmokeClient(
            api_base_url=args.api_base_url,
            user_id=args.user_id,
            tenant_id=args.tenant_id,
        )
    )
    print("Local smoke completed:")
    for key, value in result.items():
        print(f"  {key}={value}")


if __name__ == "__main__":
    asyncio.run(main())
