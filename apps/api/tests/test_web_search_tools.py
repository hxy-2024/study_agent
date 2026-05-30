import json

import httpx
import pytest

from app.domain.session_tutor_graph.tools import _tavily_search


@pytest.mark.anyio
async def test_tavily_search_posts_query_and_maps_results() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Retrieval practice",
                        "url": "https://example.test/retrieval",
                        "content": "Retrieval practice strengthens recall.",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await _tavily_search(
            client=client,
            query="retrieval practice",
            max_results=3,
            api_key="tavily-key",
        )

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["authorization"] == "Bearer tavily-key"
    assert json.loads(captured["payload"])["query"] == "retrieval practice"
    assert results == [
        {
            "title": "Retrieval practice",
            "url": "https://example.test/retrieval",
            "snippet": "Retrieval practice strengthens recall.",
        }
    ]


@pytest.mark.anyio
async def test_tavily_search_requires_api_key() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as client:
        with pytest.raises(ValueError, match="Tavily API key is not configured"):
            await _tavily_search(
                client=client,
                query="retrieval practice",
                max_results=3,
                api_key="",
            )
