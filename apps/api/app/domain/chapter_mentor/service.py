import uuid
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source
from app.domain.chapter_mentor.schemas import (
    ChapterMentorCitationResponse,
    ChapterMentorResponse,
)
from app.domain.chapter_study.service import load_chapter_context
from app.domain.rag.embeddings import EmbeddingProvider
from app.domain.rag.retrieval import RetrievedChunk, retrieve_chunks


ANSWER_EXCERPT_CHARS = 220
CITATION_EXCERPT_CHARS = 320


class AnswerProvider(Protocol):
    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict[uuid.UUID, str],
    ) -> ChapterMentorResponse:
        """Generate a grounded chapter answer."""


def _clip_text(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}..."


def compose_grounded_answer(
    question: str,
    chunks: Sequence[RetrievedChunk],
    source_filenames: dict[uuid.UUID, str],
) -> ChapterMentorResponse:
    citations = [
        ChapterMentorCitationResponse(
            chunk_id=chunk.id,
            source_id=chunk.source_id,
            source_filename=source_filenames.get(chunk.source_id, "Unknown source"),
            chunk_index=chunk.chunk_index,
            text=_clip_text(chunk.text, CITATION_EXCERPT_CHARS),
        )
        for chunk in chunks
    ]

    if not chunks:
        return ChapterMentorResponse(
            question=question,
            answer=(
                "I could not find enough source material to answer reliably. "
                "Upload or reprocess material related to this chapter first."
            ),
            citations=[],
        )

    evidence_lines = [
        f"{index}. {_clip_text(chunk.text, ANSWER_EXCERPT_CHARS)}"
        for index, chunk in enumerate(chunks[:3], start=1)
    ]
    answer = (
        "Based on the current chapter evidence, focus on these points:\n"
        + "\n".join(evidence_lines)
        + "\n\nRestate these ideas in your own words, then compare them with the chapter goal."
    )
    return ChapterMentorResponse(question=question, answer=answer, citations=citations)


async def load_source_filenames(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    source_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, str]:
    if not source_ids:
        return {}

    rows = await session.execute(
        select(Source.id, Source.filename).where(
            Source.id.in_(source_ids),
            Source.tenant_id == tenant_id,
            Source.study_space_id == study_space_id,
        )
    )
    return {source_id: filename for source_id, filename in rows.all()}


async def ask_chapter_mentor(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
    question: str,
    embedding_provider: EmbeddingProvider,
    answer_provider: AnswerProvider,
    limit: int = 5,
) -> ChapterMentorResponse:
    chapter, _route, _study_space, _route_chapters, _evidence = await load_chapter_context(
        session=session,
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )
    query = f"{chapter.title}\n{chapter.goal}\n{question}"
    chunks = await retrieve_chunks(
        session=session,
        tenant_id=tenant_id,
        study_space_id=chapter.study_space_id,
        query=query,
        limit=limit,
        embedding_provider=embedding_provider,
    )
    source_filenames = await load_source_filenames(
        session=session,
        tenant_id=tenant_id,
        study_space_id=chapter.study_space_id,
        source_ids=[chunk.source_id for chunk in chunks],
    )
    return await answer_provider.answer(
        question=question,
        chunks=chunks,
        source_filenames=source_filenames,
    )
