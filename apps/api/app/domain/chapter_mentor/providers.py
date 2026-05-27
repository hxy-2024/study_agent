from typing import Protocol

import httpx

from app.core.config import Settings
from app.domain.chapter_mentor.schemas import ChapterMentorResponse
from app.domain.chapter_mentor.service import compose_grounded_answer
from app.domain.rag.retrieval import RetrievedChunk


SYSTEM_PROMPT = (
    "You are an AI study mentor. Answer only from the provided chapter evidence. "
    "If evidence is insufficient, say so clearly. Keep the answer concise and actionable."
)


class AnswerProvider(Protocol):
    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
    ) -> ChapterMentorResponse:
        """Generate a grounded chapter answer."""


class DeterministicAnswerProvider:
    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict,
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
    ) -> ChapterMentorResponse:
        fallback = compose_grounded_answer(
            question=question,
            chunks=chunks,
            source_filenames=source_filenames,
        )
        if not chunks:
            return fallback

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_prompt(question, chunks, source_filenames)},
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
    ) -> str:
        evidence = "\n\n".join(
            (
                f"[{index}] source={source_filenames.get(chunk.source_id, 'Unknown source')} "
                f"chunk={chunk.chunk_index}\n{chunk.text}"
            )
            for index, chunk in enumerate(chunks, start=1)
        )
        return f"Question:\n{question}\n\nChapter evidence:\n{evidence}"

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
