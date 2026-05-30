import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Chapter,
    ChapterAnnotation,
    Message,
    Quiz,
    Session,
    Source,
    SourceChunk,
    StudySpace,
    LearningRoute,
)


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _item(obj: Any, fields: list[str]) -> dict[str, Any]:
    return {field: _value(getattr(obj, field, None)) for field in fields}


def serialize_study_space_export(
    *,
    study_space: StudySpace,
    sources: list[Source],
    chunks: list[SourceChunk],
    routes: list[LearningRoute],
    chapters: list[Chapter],
    sessions: list[Session],
    messages: list[Message],
    quizzes: list[Quiz],
    notes: list[ChapterAnnotation],
) -> dict[str, Any]:
    chunks_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        chunks_by_source[str(chunk.source_id)].append(
            _item(chunk, ["id", "source_id", "chunk_index", "text", "citation", "is_active", "created_at"])
        )

    messages_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for message in messages:
        messages_by_session[str(message.session_id)].append(_item(message, ["id", "session_id", "role", "content", "created_at"]))

    return {
        "study_space": _item(
            study_space,
            [
                "id",
                "tenant_id",
                "name",
                "goal",
                "level",
                "intensity",
                "target_days",
                "status",
                "route_outline",
                "created_at",
                "updated_at",
            ],
        ),
        "sources": [
            {
                **_item(
                    source,
                    ["id", "filename", "content_type", "object_key", "status", "error_message", "created_at"],
                ),
                "chunks": chunks_by_source.get(str(source.id), []),
            }
            for source in sources
        ],
        "routes": [_item(route, ["id", "version", "status", "title", "summary", "generation_strategy", "created_at", "activated_at"]) for route in routes],
        "chapters": [
            _item(
                chapter,
                [
                    "id",
                    "learning_route_id",
                    "order_index",
                    "title",
                    "goal",
                    "summary",
                    "estimated_days",
                    "status",
                    "source_chunk_refs",
                    "created_at",
                ],
            )
            for chapter in chapters
        ],
        "sessions": [
            {
                **_item(session, ["id", "chapter_id", "title", "status", "summary", "created_at", "updated_at"]),
                "messages": messages_by_session.get(str(session.id), []),
            }
            for session in sessions
        ],
        "quizzes": [_item(quiz, ["id", "chapter_id", "title", "status", "generation_strategy", "question_count", "created_at", "updated_at"]) for quiz in quizzes],
        "notes": [_item(note, ["id", "chapter_id", "source_chunk_id", "kind", "content", "quote", "anchor", "created_at", "updated_at"]) for note in notes],
    }


def format_study_space_markdown(payload: dict[str, Any]) -> str:
    space = payload["study_space"]
    lines = [
        f"# {space.get('name', 'Study space')}",
        "",
        f"Goal: {space.get('goal', '')}",
        "",
        "## Sources",
    ]
    for source in payload.get("sources", []):
        lines.append(f"- {source.get('filename')} ({source.get('status')})")
        for chunk in source.get("chunks", [])[:5]:
            lines.append(f"  - Chunk {chunk.get('chunk_index')}: {chunk.get('text')}")

    lines.extend(["", "## Routes"])
    for route in payload.get("routes", []):
        lines.append(f"- {route.get('title')} ({route.get('status')})")

    lines.extend(["", "## Chapters"])
    for chapter in payload.get("chapters", []):
        lines.append(f"- {chapter.get('order_index', '')}. {chapter.get('title')} ({chapter.get('status')})")
        if chapter.get("summary"):
            lines.append(f"  {chapter.get('summary')}")

    lines.extend(["", "## Mentor Sessions"])
    for session in payload.get("sessions", []):
        lines.append(f"- {session.get('title')} ({session.get('status')})")
        for message in session.get("messages", [])[:8]:
            lines.append(f"  - {message.get('role')}: {message.get('content')}")

    lines.extend(["", "## Quizzes"])
    for quiz in payload.get("quizzes", []):
        lines.append(f"- {quiz.get('title')} ({quiz.get('status')})")

    lines.extend(["", "## Notes"])
    for note in payload.get("notes", []):
        content = note.get("content") or note.get("quote") or ""
        lines.append(f"- {content}")

    return "\n".join(lines).strip() + "\n"


async def export_study_space(session: AsyncSession, tenant_id: uuid.UUID, study_space_id: uuid.UUID) -> dict[str, Any]:
    study_space = await session.scalar(
        select(StudySpace).where(StudySpace.tenant_id == tenant_id, StudySpace.id == study_space_id)
    )
    if study_space is None:
        raise ValueError("Study space not found for tenant")

    source_rows = await session.scalars(select(Source).where(Source.tenant_id == tenant_id, Source.study_space_id == study_space_id))
    sources = list(source_rows)
    chunk_rows = await session.scalars(
        select(SourceChunk)
        .where(SourceChunk.tenant_id == tenant_id, SourceChunk.study_space_id == study_space_id)
        .order_by(SourceChunk.source_id, SourceChunk.chunk_index)
    )
    route_rows = await session.scalars(select(LearningRoute).where(LearningRoute.tenant_id == tenant_id, LearningRoute.study_space_id == study_space_id))
    chapter_rows = await session.scalars(
        select(Chapter)
        .where(Chapter.tenant_id == tenant_id, Chapter.study_space_id == study_space_id)
        .order_by(Chapter.order_index)
    )
    session_rows = await session.scalars(
        select(Session).where(Session.tenant_id == tenant_id, Session.study_space_id == study_space_id).order_by(Session.created_at)
    )
    message_rows = await session.scalars(
        select(Message).where(Message.tenant_id == tenant_id, Message.study_space_id == study_space_id).order_by(Message.created_at)
    )
    quiz_rows = await session.scalars(select(Quiz).where(Quiz.tenant_id == tenant_id, Quiz.study_space_id == study_space_id))
    note_rows = await session.scalars(
        select(ChapterAnnotation).where(ChapterAnnotation.tenant_id == tenant_id, ChapterAnnotation.study_space_id == study_space_id)
    )

    return serialize_study_space_export(
        study_space=study_space,
        sources=sources,
        chunks=list(chunk_rows),
        routes=list(route_rows),
        chapters=list(chapter_rows),
        sessions=list(session_rows),
        messages=list(message_rows),
        quizzes=list(quiz_rows),
        notes=list(note_rows),
    )
