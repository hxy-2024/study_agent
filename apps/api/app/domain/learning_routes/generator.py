import re
import uuid
from dataclasses import dataclass
from typing import Protocol


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
