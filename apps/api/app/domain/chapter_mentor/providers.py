import json
from collections.abc import AsyncIterator
from typing import Protocol
from pathlib import Path

import httpx

from app.core.config import Settings
from app.domain.chapter_mentor.schemas import ChapterMentorResponse
from app.domain.chapter_mentor.service import compose_grounded_answer
from app.domain.local_settings.service import load_local_ai_settings
from app.domain.rag.retrieval import RetrievedChunk

WebSearchResult = dict[str, str]
AnswerStyle = str
ThinkingEffort = str


SYSTEM_PROMPT = (
    "You are an AI study mentor. Prefer the provided chapter evidence. "
    "Use web search context only as supplemental fresh context, and clearly distinguish it "
    "from uploaded study material. If evidence is insufficient, say so clearly. "
    "Keep the answer concise and actionable."
)

STYLE_INSTRUCTIONS: dict[AnswerStyle, str] = {
    "concise": "Use a concise explanation with direct next steps.",
    "socratic": "Use a Socratic style: ask guiding questions before giving conclusions.",
    "exam_review": "Use an exam review style: emphasize likely test points, traps, and recall cues.",
    "code_tutor": "Use a code tutor style: prefer concrete examples, debugging checks, and implementation steps.",
}

THINKING_INSTRUCTIONS: dict[ThinkingEffort, str] = {
    "low": "Use low reasoning depth: answer briefly, skip optional background, and give the next action quickly.",
    "medium": "Use medium reasoning depth: explain the key steps and tradeoffs without over-expanding.",
    "high": "Use high reasoning depth: work through the problem carefully, structure the answer in steps, and verify assumptions without revealing hidden chain-of-thought.",
}


class AnswerProvider(Protocol):
    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
        thinking_effort: ThinkingEffort = "medium",
    ) -> ChapterMentorResponse:
        """Generate a grounded chapter answer."""

    async def stream_answer_text(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
        thinking_effort: ThinkingEffort = "medium",
    ) -> AsyncIterator[str]:
        """Generate answer text incrementally when supported."""


class DeterministicAnswerProvider:
    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
        thinking_effort: ThinkingEffort = "medium",
    ) -> ChapterMentorResponse:
        return compose_grounded_answer(
            question=question,
            chunks=chunks,
            source_filenames=source_filenames,
        )

    async def stream_answer_text(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
        thinking_effort: ThinkingEffort = "medium",
    ) -> AsyncIterator[str]:
        response = await self.answer(
            question=question,
            chunks=chunks,
            source_filenames=source_filenames,
            web_search_results=web_search_results,
            thinking_effort=thinking_effort,
        )
        yield response.answer


class OpenAICompatibleAnswerProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        answer_style: AnswerStyle = "concise",
        system_prompt: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.answer_style = answer_style
        self.system_prompt = system_prompt.strip()
        self.client = client

    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
        thinking_effort: ThinkingEffort = "medium",
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
                {"role": "system", "content": self._system_prompt(thinking_effort)},
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

    async def stream_answer_text(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
        web_search_results: list[WebSearchResult] | None = None,
        thinking_effort: ThinkingEffort = "medium",
    ) -> AsyncIterator[str]:
        fallback = compose_grounded_answer(
            question=question,
            chunks=chunks,
            source_filenames=source_filenames,
        )
        web_results = web_search_results or []
        if not chunks and not web_results:
            yield fallback.answer
            return

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt(thinking_effort)},
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
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            if self.client is not None:
                async with self.client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                ) as response:
                    response.raise_for_status()
                    async for delta in self._iter_stream_deltas(response):
                        yield delta
                return

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for delta in self._iter_stream_deltas(response):
                        yield delta
        except Exception:
            yield fallback.answer

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

    def _system_prompt(self, thinking_effort: ThinkingEffort = "medium") -> str:
        style_instruction = STYLE_INSTRUCTIONS.get(self.answer_style, STYLE_INSTRUCTIONS["concise"])
        thinking_instruction = THINKING_INSTRUCTIONS.get(thinking_effort, THINKING_INSTRUCTIONS["medium"])
        base_prompt = self.system_prompt or SYSTEM_PROMPT
        return f"{base_prompt} {style_instruction} {thinking_instruction}"

    def _extract_answer(self, payload: dict) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("LLM response did not include choices")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM response did not include answer content")
        return content.strip()

    async def _iter_stream_deltas(self, response: httpx.Response) -> AsyncIterator[str]:
        async for line in response.aiter_lines():
            line = line.strip()
            if not line or line == "data: [DONE]":
                continue
            if not line.startswith("data: "):
                continue
            try:
                payload = json.loads(line.removeprefix("data: "))
            except json.JSONDecodeError:
                continue
            choices = payload.get("choices") or []
            if not choices:
                continue
            content = choices[0].get("delta", {}).get("content")
            if isinstance(content, str) and content:
                yield content


def create_answer_provider(
    settings: Settings,
    *,
    agent_layer: str = "chapter_mentor",
    model_override: str | None = None,
) -> AnswerProvider:
    local_settings = (
        load_local_ai_settings(path=settings.local_settings_path)
        if Path(settings.local_settings_path).exists()
        else None
    )
    provider_name = (
        local_settings.llm_provider if local_settings is not None else settings.llm_provider
    ).strip().lower()
    api_key = (local_settings.llm_api_key if local_settings is not None else "") or settings.llm_api_key
    system_prompt = ""
    if local_settings is not None:
        system_prompt = (
            local_settings.session_tutor_system_prompt
            if agent_layer == "session_tutor"
            else local_settings.chapter_mentor_system_prompt
        )
    openai_compatible_provider = provider_name not in {"", "deterministic", "local"}
    if openai_compatible_provider and api_key:
        model = (model_override or "").strip()
        return OpenAICompatibleAnswerProvider(
            base_url=(local_settings.llm_base_url if local_settings is not None else "") or settings.llm_base_url,
            api_key=api_key,
            model=model or (local_settings.llm_model if local_settings is not None else "") or settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            answer_style=(local_settings.answer_style if local_settings is not None else "concise"),
            system_prompt=system_prompt,
        )
    return DeterministicAnswerProvider()
