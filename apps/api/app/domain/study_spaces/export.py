import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRun,
    Chapter,
    ChapterAnnotation,
    ChapterMentorState,
    LearningRoute,
    MasteryRecord,
    Message,
    MessageCitation,
    PlannerAction,
    Quiz,
    QuizQuestion,
    QuizSubmission,
    Session,
    Source,
    SourceChunk,
    SpacePlannerState,
    StudySpace,
)

EXPORT_SCHEMA_VERSION = 1


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, list):
        return [_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _value(item) for key, item in value.items()}
    return value


def _item(obj: Any, fields: list[str]) -> dict[str, Any]:
    return {field: _value(getattr(obj, field, None)) for field in fields}


def _message_item(message: Any, citations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **_item(message, ["id", "session_id", "role", "content", "created_at"]),
        "metadata": _value(getattr(message, "metadata_", None) or {}),
        "citations": citations,
    }


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
    message_citations: list[MessageCitation] | None = None,
    quiz_questions: list[QuizQuestion] | None = None,
    quiz_submissions: list[QuizSubmission] | None = None,
    mastery_records: list[MasteryRecord] | None = None,
    mentor_states: list[ChapterMentorState] | None = None,
    planner_states: list[SpacePlannerState] | None = None,
    planner_actions: list[PlannerAction] | None = None,
    agent_runs: list[AgentRun] | None = None,
) -> dict[str, Any]:
    message_citations = message_citations or []
    quiz_questions = quiz_questions or []
    quiz_submissions = quiz_submissions or []
    mastery_records = mastery_records or []
    mentor_states = mentor_states or []
    planner_states = planner_states or []
    planner_actions = planner_actions or []
    agent_runs = agent_runs or []

    chunks_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        chunks_by_source[str(chunk.source_id)].append(
            _item(
                chunk,
                ["id", "source_id", "chunk_index", "text", "token_count", "citation", "is_active", "created_at"],
            )
        )

    citations_by_message: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for citation in message_citations:
        citations_by_message[str(citation.message_id)].append(
            _item(citation, ["id", "message_id", "source_id", "source_chunk_id", "quote", "citation", "created_at"])
        )

    messages_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for message in messages:
        messages_by_session[str(message.session_id)].append(
            _message_item(message, citations_by_message.get(str(message.id), []))
        )

    questions_by_quiz: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for question in quiz_questions:
        questions_by_quiz[str(question.quiz_id)].append(
            _item(
                question,
                [
                    "id",
                    "quiz_id",
                    "chapter_id",
                    "order_index",
                    "prompt",
                    "options",
                    "correct_option_index",
                    "explanation",
                    "evidence",
                    "created_at",
                ],
            )
        )

    submissions_by_quiz: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for submission in quiz_submissions:
        submissions_by_quiz[str(submission.quiz_id)].append(
            _item(
                submission,
                [
                    "id",
                    "quiz_id",
                    "chapter_id",
                    "user_id",
                    "answers",
                    "score_percent",
                    "correct_count",
                    "question_count",
                    "results",
                    "weak_points",
                    "created_at",
                ],
            )
        )

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "study_space": _item(
            study_space,
            [
                "id",
                "tenant_id",
                "owner_user_id",
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
                    [
                        "id",
                        "tenant_id",
                        "study_space_id",
                        "filename",
                        "content_type",
                        "object_key",
                        "status",
                        "error_message",
                        "created_at",
                    ],
                ),
                "chunks": chunks_by_source.get(str(source.id), []),
            }
            for source in sources
        ],
        "routes": [
            _item(
                route,
                [
                    "id",
                    "tenant_id",
                    "study_space_id",
                    "version",
                    "status",
                    "title",
                    "summary",
                    "generation_strategy",
                    "created_at",
                    "activated_at",
                ],
            )
            for route in routes
        ],
        "chapters": [
            _item(
                chapter,
                [
                    "id",
                    "tenant_id",
                    "study_space_id",
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
                **_item(
                    session,
                    ["id", "tenant_id", "study_space_id", "chapter_id", "title", "status", "summary", "created_at", "updated_at"],
                ),
                "messages": messages_by_session.get(str(session.id), []),
            }
            for session in sessions
        ],
        "quizzes": [
            {
                **_item(
                    quiz,
                    [
                        "id",
                        "tenant_id",
                        "user_id",
                        "study_space_id",
                        "chapter_id",
                        "title",
                        "status",
                        "generation_strategy",
                        "question_count",
                        "created_at",
                        "updated_at",
                    ],
                ),
                "questions": questions_by_quiz.get(str(quiz.id), []),
                "submissions": submissions_by_quiz.get(str(quiz.id), []),
            }
            for quiz in quizzes
        ],
        "mastery_records": [
            _item(
                record,
                [
                    "id",
                    "tenant_id",
                    "user_id",
                    "study_space_id",
                    "chapter_id",
                    "score_percent",
                    "level",
                    "weak_points",
                    "last_quiz_submission_id",
                    "updated_at",
                ],
            )
            for record in mastery_records
        ],
        "mentor_states": [
            _item(
                state,
                [
                    "id",
                    "tenant_id",
                    "study_space_id",
                    "chapter_id",
                    "summary",
                    "weak_points",
                    "next_actions",
                    "evidence",
                    "source_session_count",
                    "source_message_count",
                    "created_at",
                    "updated_at",
                ],
            )
            for state in mentor_states
        ],
        "planner_states": [
            _item(
                state,
                [
                    "id",
                    "tenant_id",
                    "user_id",
                    "study_space_id",
                    "summary",
                    "next_chapter_id",
                    "risk_chapters",
                    "review_recommendations",
                    "route_adjustments",
                    "evidence",
                    "created_at",
                    "updated_at",
                ],
            )
            for state in planner_states
        ],
        "planner_actions": [
            _item(
                action,
                [
                    "id",
                    "tenant_id",
                    "user_id",
                    "study_space_id",
                    "chapter_id",
                    "source_planner_state_id",
                    "action_type",
                    "status",
                    "title",
                    "rationale",
                    "payload",
                    "created_at",
                    "updated_at",
                ],
            )
            for action in planner_actions
        ],
        "agent_runs": [
            _item(
                run,
                [
                    "id",
                    "tenant_id",
                    "study_space_id",
                    "session_id",
                    "message_id",
                    "agent_type",
                    "status",
                    "model",
                    "input_payload",
                    "output_payload",
                    "error_message",
                    "latency_ms",
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "created_at",
                    "completed_at",
                ],
            )
            for run in agent_runs
        ],
        "notes": [
            _item(
                note,
                [
                    "id",
                    "tenant_id",
                    "user_id",
                    "study_space_id",
                    "chapter_id",
                    "source_chunk_id",
                    "kind",
                    "content",
                    "quote",
                    "anchor",
                    "created_at",
                    "updated_at",
                ],
            )
            for note in notes
        ],
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
    citation_rows = await session.scalars(
        select(MessageCitation)
        .join(Message, MessageCitation.message_id == Message.id)
        .where(MessageCitation.tenant_id == tenant_id, Message.study_space_id == study_space_id)
        .order_by(MessageCitation.created_at)
    )
    quiz_rows = await session.scalars(select(Quiz).where(Quiz.tenant_id == tenant_id, Quiz.study_space_id == study_space_id))
    question_rows = await session.scalars(
        select(QuizQuestion)
        .join(Quiz, QuizQuestion.quiz_id == Quiz.id)
        .where(QuizQuestion.tenant_id == tenant_id, Quiz.study_space_id == study_space_id)
        .order_by(QuizQuestion.quiz_id, QuizQuestion.order_index)
    )
    submission_rows = await session.scalars(
        select(QuizSubmission)
        .join(Quiz, QuizSubmission.quiz_id == Quiz.id)
        .where(QuizSubmission.tenant_id == tenant_id, Quiz.study_space_id == study_space_id)
        .order_by(QuizSubmission.created_at)
    )
    mastery_rows = await session.scalars(
        select(MasteryRecord).where(MasteryRecord.tenant_id == tenant_id, MasteryRecord.study_space_id == study_space_id)
    )
    mentor_state_rows = await session.scalars(
        select(ChapterMentorState).where(ChapterMentorState.tenant_id == tenant_id, ChapterMentorState.study_space_id == study_space_id)
    )
    planner_state_rows = await session.scalars(
        select(SpacePlannerState).where(SpacePlannerState.tenant_id == tenant_id, SpacePlannerState.study_space_id == study_space_id)
    )
    planner_action_rows = await session.scalars(
        select(PlannerAction).where(PlannerAction.tenant_id == tenant_id, PlannerAction.study_space_id == study_space_id)
    )
    agent_run_rows = await session.scalars(
        select(AgentRun)
        .where(AgentRun.tenant_id == tenant_id, AgentRun.study_space_id == study_space_id)
        .order_by(AgentRun.created_at)
    )
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
        message_citations=list(citation_rows),
        quiz_questions=list(question_rows),
        quiz_submissions=list(submission_rows),
        mastery_records=list(mastery_rows),
        mentor_states=list(mentor_state_rows),
        planner_states=list(planner_state_rows),
        planner_actions=list(planner_action_rows),
        agent_runs=list(agent_run_rows),
    )
