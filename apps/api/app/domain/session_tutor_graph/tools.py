from typing import Any, TypedDict

import httpx
from langchain_core.tools import tool

from app.core.config import get_settings
from app.domain.local_settings.service import load_local_ai_settings


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


def _web_search_config() -> tuple[str, str]:
    settings = get_settings()
    local_settings = load_local_ai_settings(path=settings.local_settings_path)
    provider = (local_settings.web_search_provider or settings.session_tutor_web_search_provider).strip().lower()
    tavily_api_key = local_settings.tavily_api_key or settings.tavily_api_key
    return provider, tavily_api_key


async def _duckduckgo_search(
    client: httpx.AsyncClient,
    query: str,
    max_results: int,
) -> list[WebSearchResult]:
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


async def _tavily_search(
    client: httpx.AsyncClient,
    query: str,
    max_results: int,
    api_key: str,
) -> list[WebSearchResult]:
    if not api_key:
        raise ValueError("Tavily API key is not configured")

    response = await client.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        },
    )
    response.raise_for_status()
    payload = response.json()
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return []

    results: list[WebSearchResult] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        content = item.get("content")
        if isinstance(title, str) and isinstance(url, str) and isinstance(content, str) and url:
            results.append(WebSearchResult(title=title[:120], url=url, snippet=content[:360]))
    return results[:max_results]


@tool("web_search")
async def web_search_tool(
    query: str,
    max_results: int = 3,
    timeout_seconds: int = 5,
) -> list[WebSearchResult]:
    """Search the public web for fresh context that can supplement local study evidence."""
    if not query.strip() or max_results <= 0:
        return []

    provider, tavily_api_key = _web_search_config()
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        if provider == "tavily":
            return await _tavily_search(client, query, max_results, tavily_api_key)
        return await _duckduckgo_search(client, query, max_results)
