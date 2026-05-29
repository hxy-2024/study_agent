from typing import Protocol

import httpx

from app.core.config import Settings
from app.domain.chapter_mentor.schemas import ChapterMentorResponse
from app.domain.chapter_mentor.service import compose_grounded_answer
from app.domain.rag.retrieval import RetrievedChunk

WebSearchResult = dict[str, str]


SYSTEM_PROMPT = (
    "You are an AI study mentor. Prefer the provided chapter evidence. "
    "Use web search context only as supplemental fresh context, and clearly distinguish it "
    "from uploaded study material. If evidence is insufficient, say so clearly. "
    "Keep the answer concise and actionable."
)


class AnswerProvider(Protocol):
    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
    ) -> ChapterMentorResponse:
        """Generate a grounded chapter answer."""


class DeterministicAnswerProvider:
    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
    ) -> ChapterMentorResponse:
        return compose_grounded_answer(
            question=question,
            chunks=chunks,
            source_filenames=source_filenames,
        )


class OpenAICompatibleAnswerProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = client

    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
    ) -> ChapterMentorResponse:
        fallback = compose_grounded_answer(
            question=question,
            chunks=chunks,
            source_filenames=source_filenames,
        )
        web_results = web_search_results or []
        if not chunks and not web_results:
            return fallback

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": self._build_user_prompt(
                        question,
                        chunks,
                        source_filenames,
                        web_results,
                    ),
                },
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        if self.client is not None:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            answer_text = self._extract_answer(response.json())
            return fallback.model_copy(update={"answer": answer_text})

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            answer_text = self._extract_answer(response.json())
            return fallback.model_copy(update={"answer": answer_text})

    def _build_user_prompt(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
    ) -> str:
        evidence = "\n\n".join(
            (
                f"[{index}] source={source_filenames.get(chunk.source_id, 'Unknown source')} "
                f"chunk={chunk.chunk_index}\n{chunk.text}"
            )
            for index, chunk in enumerate(chunks, start=1)
        )
        web_context = "\n\n".join(
            (
                f"[web:{index}] title={result.get('title', 'Web result')}\n"
                f"url={result.get('url', '')}\n"
                f"snippet={result.get('snippet', '')}"
            )
            for index, result in enumerate(web_search_results or [], start=1)
        )
        return (
            f"Question:\n{question}\n\n"
            f"Chapter evidence:\n{evidence or 'No uploaded chapter evidence retrieved.'}\n\n"
            f"Web search context:\n{web_context or 'No web search context returned.'}"
        )

    def _extract_answer(self, payload: dict) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("LLM response did not include choices")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM response did not include answer content")
        return content.strip()


def create_answer_provider(settings: Settings) -> AnswerProvider:
    provider_name = settings.llm_provider.strip().lower()
    if provider_name in {"openai", "openai-compatible"} and settings.llm_api_key:
        return OpenAICompatibleAnswerProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return DeterministicAnswerProvider()
