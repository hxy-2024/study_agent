from typing import Any, TypedDict

import httpx
from langchain_core.tools import tool


class WebSearchResult(TypedDict):
    title: str
    url: str
    snippet: str


def _collect_related_topics(items: list[dict[str, Any]], results: list[WebSearchResult]) -> None:
    for item in items:
        nested = item.get("Topics")
        if isinstance(nested, list):
            _collect_related_topics(nested, results)
            continue

        text = item.get("Text")
        url = item.get("FirstURL")
        if isinstance(text, str) and isinstance(url, str) and text and url:
            title = text.split(" - ", 1)[0][:120]
            results.append(WebSearchResult(title=title, url=url, snippet=text[:360]))


@tool("web_search")
async def web_search_tool(
    query: str,
    max_results: int = 3,
    timeout_seconds: int = 5,
) -> list[WebSearchResult]:
    """Search the public web for fresh context that can supplement local study evidence."""
    if not query.strip() or max_results <= 0:
        return []

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        response = await client.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            },
        )
        response.raise_for_status()
        payload = response.json()

    results: list[WebSearchResult] = []
    abstract = payload.get("AbstractText")
    abstract_url = payload.get("AbstractURL")
    heading = payload.get("Heading")
    if isinstance(abstract, str) and isinstance(abstract_url, str) and abstract and abstract_url:
        results.append(
            WebSearchResult(
                title=str(heading or "Web result")[:120],
                url=abstract_url,
                snippet=abstract[:360],
            )
        )

    related_topics = payload.get("RelatedTopics")
    if isinstance(related_topics, list):
        _collect_related_topics(related_topics, results)

    return results[:max_results]
