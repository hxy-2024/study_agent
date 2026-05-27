import pytest

from scripts.smoke_local import SmokeClient, run_smoke


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls = []

    async def get(self, path):
        self.calls.append(("GET", path, None))
        if path == "/health":
            return {"status": "ok"}
        if path.endswith("/chunks"):
            return {"chunks": [{"id": "chunk-1", "text": "RAG evidence"}]}
        raise AssertionError(f"Unexpected GET {path}")

    async def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        if path == "/study-spaces":
            return {"id": "space-1"}
        if path == "/uploads/presign":
            return {"source_id": "source-1", "upload_url": "http://storage/upload"}
        if path == "/sources/source-1/uploaded":
            return {"source": {"id": "source-1", "status": "uploaded"}}
        if path == "/ingestion/sources/source-1/run":
            return {"status": "completed", "chunk_count": 1}
        if path == "/study-spaces/space-1/route-drafts":
            return {"chapters": [{"id": "chapter-1"}]}
        if path == "/chapters/chapter-1/mentor/questions":
            return {"answer": "Grounded answer", "citations": [{"chunk_id": "chunk-1"}]}
        if path == "/chapters/chapter-1/complete":
            return {"chapter": {"id": "chapter-1", "status": "completed"}}
        raise AssertionError(f"Unexpected POST {path}")

    async def put_bytes(self, url, content, content_type):
        self.calls.append(("PUT", url, {"content": content.decode(), "content_type": content_type}))


@pytest.mark.anyio
async def test_run_smoke_executes_full_local_flow() -> None:
    fake_http = FakeHttpClient()
    client = SmokeClient(
        api_base_url="http://api.test/api/v1",
        user_id="user-1",
        tenant_id="tenant-1",
        http=fake_http,
    )

    result = await run_smoke(client)

    assert result["health"] == "ok"
    assert result["space_id"] == "space-1"
    assert result["source_id"] == "source-1"
    assert result["chunk_count"] == 1
    assert result["chapter_id"] == "chapter-1"
    assert result["mentor_citation_count"] == 1
    assert result["chapter_status"] == "completed"
    assert fake_http.calls == [
        ("GET", "/health", None),
        (
            "POST",
            "/study-spaces",
            {
                "name": "Local smoke study space",
                "goal": "Understand retrieval augmented generation fundamentals.",
                "level": "beginner",
                "intensity": "normal",
                "target_days": 7,
            },
        ),
        (
            "POST",
            "/uploads/presign",
            {
                "study_space_id": "space-1",
                "filename": "local-smoke.md",
                "content_type": "text/markdown",
            },
        ),
        ("PUT", "http://storage/upload", {"content": "# RAG fundamentals\n\nRAG retrieves evidence before answering.\n", "content_type": "text/markdown"}),
        ("POST", "/sources/source-1/uploaded", None),
        ("POST", "/ingestion/sources/source-1/run", None),
        ("GET", "/sources/source-1/chunks", None),
        ("POST", "/study-spaces/space-1/route-drafts", {"max_chapters": 3}),
        ("POST", "/chapters/chapter-1/mentor/questions", {"question": "What should I focus on first?"}),
        ("POST", "/chapters/chapter-1/complete", None),
    ]
