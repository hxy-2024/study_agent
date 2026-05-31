import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import Settings
from app.domain.local_settings.service import load_local_ai_settings


@dataclass(frozen=True)
class SourceChunkExcerpt:
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    text: str


@dataclass(frozen=True)
class RouteGenerationRequest:
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    study_space_name: str
    goal: str
    level: str
    intensity: str
    target_days: int
    max_chapters: int
    chunks: list[SourceChunkExcerpt]


@dataclass(frozen=True)
class ChapterDraft:
    title: str
    goal: str
    summary: str
    estimated_days: int
    source_chunk_refs: list[dict]


@dataclass(frozen=True)
class RouteGenerationResult:
    title: str
    summary: str
    generation_strategy: str
    chapters: list[ChapterDraft]


class RouteGenerator(Protocol):
    async def generate(self, request: RouteGenerationRequest) -> RouteGenerationResult:
        ...


class DeterministicRouteGenerator:
    MIN_CHAPTERS = 3
    MAX_CHAPTERS = 6

    async def generate(self, request: RouteGenerationRequest) -> RouteGenerationResult:
        chunk_limit = min(max(request.max_chapters, self.MIN_CHAPTERS), self.MAX_CHAPTERS)
        chunks = request.chunks[:chunk_limit]
        if chunks:
            chapters = self._chapters_from_chunks(request=request, chunks=chunks)
        else:
            chapters = self._fallback_chapters(request)

        return RouteGenerationResult(
            title=f"{request.study_space_name} learning route",
            summary=f"A {len(chapters)} chapter route for {request.goal}.",
            generation_strategy="deterministic",
            chapters=chapters,
        )

    def _chapters_from_chunks(
        self,
        request: RouteGenerationRequest,
        chunks: list[SourceChunkExcerpt],
    ) -> list[ChapterDraft]:
        chapter_count = min(
            self.MAX_CHAPTERS,
            max(self.MIN_CHAPTERS, min(request.max_chapters, len(chunks))),
        )
        days = split_days(request.target_days, chapter_count)
        chapters: list[ChapterDraft] = []
        chunk_groups = group_chunks(chunks, chapter_count)
        for index, group in enumerate(chunk_groups):
            first_chunk = group[0] if group else None
            title = title_from_text(first_chunk.text) if first_chunk else fallback_titles()[index]
            summary = (
                excerpt(" ".join(chunk.text for chunk in group), 220)
                if group
                else fallback_summaries()[index]
            )
            chapters.append(
                ChapterDraft(
                    title=title,
                    goal=f"Understand how this source material supports: {request.goal}.",
                    summary=summary,
                    estimated_days=days[index],
                    source_chunk_refs=[
                        {
                            "source_id": str(chunk.source_id),
                            "chunk_id": str(chunk.chunk_id),
                            "chunk_index": chunk.chunk_index,
                        }
                        for chunk in group
                    ],
                )
            )
        return chapters

    def _fallback_chapters(self, request: RouteGenerationRequest) -> list[ChapterDraft]:
        days = split_days(request.target_days, 3)
        return [
            ChapterDraft(
                title="Clarify the learning goal",
                goal=f"Define the scope and success criteria for {request.goal}.",
                summary="Map the target outcome, prior knowledge, and constraints before studying details.",
                estimated_days=days[0],
                source_chunk_refs=[],
            ),
            ChapterDraft(
                title="Build the core knowledge map",
                goal=f"Learn the central concepts needed to achieve {request.goal}.",
                summary="Organize the main ideas into a usable structure and connect related concepts.",
                estimated_days=days[1],
                source_chunk_refs=[],
            ),
            ChapterDraft(
                title="Review, test, and reinforce",
                goal=f"Check understanding and reinforce weak areas for {request.goal}.",
                summary="Use review, practice, and self-testing to convert the route into retained knowledge.",
                estimated_days=days[2],
                source_chunk_refs=[],
            ),
        ]


class LLMRouteGenerator:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        system_prompt: str = "",
        fallback: RouteGenerator | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.system_prompt = system_prompt.strip()
        self.fallback = fallback or DeterministicRouteGenerator()
        self.client = client

    async def generate(self, request: RouteGenerationRequest) -> RouteGenerationResult:
        if not request.chunks:
            return await self.fallback.generate(request)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(request)},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            if self.client is not None:
                response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
            response.raise_for_status()
            return self._parse_response(response.json(), request)
        except (httpx.HTTPError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return await self.fallback.generate(request)

    def _system_prompt(self) -> str:
        return self.system_prompt or (
            "You generate concise, feasible study routes from uploaded source evidence. "
            "Use the provided chunks as the primary source of truth. "
            "Return only valid JSON matching the requested schema."
        )

    def _user_prompt(self, request: RouteGenerationRequest) -> str:
        evidence = "\n\n".join(
            (
                f"[{index}] chunk_id={chunk.chunk_id} source_id={chunk.source_id} "
                f"chunk_index={chunk.chunk_index}\n{chunk.text}"
            )
            for index, chunk in enumerate(request.chunks, start=1)
        )
        return (
            "Create a practical study route.\n\n"
            f"Study space: {request.study_space_name}\n"
            f"Learning goal: {request.goal}\n"
            f"Level: {request.level}\n"
            f"Intensity: {request.intensity}\n"
            f"Target days: {request.target_days}\n"
            f"Maximum chapters: {request.max_chapters}\n\n"
            "Source evidence:\n"
            f"{evidence}\n\n"
            "Return JSON only with this schema:\n"
            "{\n"
            '  "title": "short route title",\n'
            '  "summary": "one sentence route summary",\n'
            '  "chapters": [\n'
            "    {\n"
            '      "title": "short chapter title",\n'
            '      "goal": "specific learning objective",\n'
            '      "summary": "concise, actionable chapter description",\n'
            '      "estimated_days": 1,\n'
            '      "source_chunk_indexes": [1]\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Use 3 to max_chapters chapters when possible. The sum of estimated_days should "
            "roughly match Target days. source_chunk_indexes must refer to evidence numbers above."
        )

    def _parse_response(
        self,
        payload: dict,
        request: RouteGenerationRequest,
    ) -> RouteGenerationResult:
        choices = payload.get("choices") or []
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM route response did not include content")
        parsed = json.loads(_strip_json_fence(content))
        raw_chapters = parsed.get("chapters")
        if not isinstance(raw_chapters, list) or not raw_chapters:
            raise ValueError("LLM route response did not include chapters")

        max_chapters = max(1, request.max_chapters)
        chapters: list[ChapterDraft] = []
        for raw in raw_chapters[:max_chapters]:
            if not isinstance(raw, dict):
                continue
            title = _clean_text(raw.get("title"), "Source-guided chapter", 120)
            goal = _clean_text(raw.get("goal"), f"Study evidence for: {request.goal}.", 260)
            summary = _clean_text(raw.get("summary"), "Study and practice the cited material.", 500)
            estimated_days = _positive_int(raw.get("estimated_days"), 1)
            chapters.append(
                ChapterDraft(
                    title=title,
                    goal=goal,
                    summary=summary,
                    estimated_days=estimated_days,
                    source_chunk_refs=_chunk_refs_from_indexes(
                        raw.get("source_chunk_indexes"),
                        request.chunks,
                    ),
                )
            )
        if not chapters:
            raise ValueError("LLM route response chapters were invalid")
        return RouteGenerationResult(
            title=_clean_text(
                parsed.get("title"),
                f"{request.study_space_name} learning route",
                160,
            ),
            summary=_clean_text(
                parsed.get("summary"),
                f"A {len(chapters)} chapter route for {request.goal}.",
                500,
            ),
            generation_strategy="llm_rag",
            chapters=chapters,
        )


def create_route_generator(settings: Settings) -> RouteGenerator:
    local_settings = (
        load_local_ai_settings(path=settings.local_settings_path)
        if Path(settings.local_settings_path).exists()
        else None
    )
    provider_name = (
        local_settings.llm_provider if local_settings is not None else settings.llm_provider
    ).strip().lower()
    api_key = (local_settings.llm_api_key if local_settings is not None else "") or settings.llm_api_key
    openai_compatible_provider = provider_name not in {"", "deterministic", "local"}
    if not openai_compatible_provider or not api_key:
        return DeterministicRouteGenerator()
    return LLMRouteGenerator(
        base_url=(local_settings.llm_base_url if local_settings is not None else "") or settings.llm_base_url,
        api_key=api_key,
        model=(local_settings.llm_model if local_settings is not None else "") or settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        system_prompt=(local_settings.main_agent_system_prompt if local_settings is not None else ""),
    )


def split_days(target_days: int, chapter_count: int) -> list[int]:
    count = max(1, chapter_count)
    total = max(count, target_days)
    base = total // count
    remainder = total % count
    return [base + (1 if index < remainder else 0) for index in range(count)]


def group_chunks(chunks: list[SourceChunkExcerpt], chapter_count: int) -> list[list[SourceChunkExcerpt]]:
    groups: list[list[SourceChunkExcerpt]] = [[] for _ in range(chapter_count)]
    for index, chunk in enumerate(chunks):
        groups[index % chapter_count].append(chunk)
    return groups


def fallback_titles() -> list[str]:
    return [
        "Clarify the learning goal",
        "Build the core knowledge map",
        "Review, test, and reinforce",
        "Connect source evidence",
        "Practice applied recall",
        "Plan next improvements",
    ]


def fallback_summaries() -> list[str]:
    return [
        "Map the target outcome, prior knowledge, and constraints before studying details.",
        "Organize the main ideas into a usable structure and connect related concepts.",
        "Use review, practice, and self-testing to convert the route into retained knowledge.",
        "Use available citations and excerpts to connect the route with source evidence.",
        "Practice retrieving key ideas and applying them in realistic study tasks.",
        "Identify weak areas and prepare the next learning iteration.",
    ]


def title_from_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    first_sentence = re.split(r"[.!?]", cleaned, maxsplit=1)[0]
    words = first_sentence.split()[:5]
    if not words:
        return "Source-guided chapter"
    return " ".join(words)


def excerpt(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "."


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _clean_text(value: object, fallback: str, limit: int) -> str:
    text = str(value).strip() if isinstance(value, str) else ""
    if not text:
        text = fallback
    return excerpt(text, limit)


def _positive_int(value: object, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(1, number)


def _chunk_refs_from_indexes(
    indexes: object,
    chunks: list[SourceChunkExcerpt],
) -> list[dict]:
    if not isinstance(indexes, list):
        return []
    refs: list[dict] = []
    for item in indexes:
        try:
            index = int(item)
        except (TypeError, ValueError):
            continue
        if index < 1 or index > len(chunks):
            continue
        chunk = chunks[index - 1]
        refs.append(
            {
                "source_id": str(chunk.source_id),
                "chunk_id": str(chunk.chunk_id),
                "chunk_index": chunk.chunk_index,
            }
        )
    return refs
