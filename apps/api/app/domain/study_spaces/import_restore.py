import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.study_spaces.export import EXPORT_SCHEMA_VERSION
from app.domain.study_spaces.schemas import StudySpaceImportResult


RESTORE_MODEL_ORDER = [
    "study_spaces",
    "sources",
    "source_chunks",
    "routes",
    "chapters",
    "sessions",
    "messages",
    "message_citations",
    "quizzes",
    "quiz_questions",
    "quiz_submissions",
    "mastery_records",
    "mentor_states",
    "planner_states",
    "planner_actions",
    "agent_runs",
    "notes",
]


class StudySpaceImportValidationError(ValueError):
    pass


class StudySpaceImportNotImplementedError(RuntimeError):
    pass


def _as_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise StudySpaceImportValidationError(f"{key} must be a list")
    return [item for item in value if isinstance(item, dict)]


def _nested(items: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    nested_items: list[dict[str, Any]] = []
    for item in items:
        value = item.get(key, [])
        if not isinstance(value, list):
            raise StudySpaceImportValidationError(f"{key} must be a list")
        nested_items.extend(nested for nested in value if isinstance(nested, dict))
    return nested_items


def _required_uuid(item: dict[str, Any], field: str, label: str) -> str:
    value = item.get(field)
    if value is None:
        raise StudySpaceImportValidationError(f"{label}.{field} is required")
    try:
        return str(uuid.UUID(str(value)))
    except ValueError as exc:
        raise StudySpaceImportValidationError(f"{label}.{field} must be a UUID") from exc


def _optional_uuid(item: dict[str, Any], field: str, label: str) -> str | None:
    value = item.get(field)
    if value in (None, ""):
        return None
    try:
        return str(uuid.UUID(str(value)))
    except ValueError as exc:
        raise StudySpaceImportValidationError(f"{label}.{field} must be a UUID") from exc


def _ensure_ref(value: str | None, valid_ids: set[str], label: str) -> None:
    if value is not None and value not in valid_ids:
        raise StudySpaceImportValidationError(f"{label} references an id that is not present in the import payload")


def _new_id_map(items: list[dict[str, Any]], label: str) -> dict[str, str]:
    return {_required_uuid(item, "id", label): str(uuid.uuid4()) for item in items}


def validate_study_space_import_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StudySpaceImportValidationError("Import payload must be an object")
    if payload.get("schema_version") != EXPORT_SCHEMA_VERSION:
        raise StudySpaceImportValidationError(
            f"Unsupported study space export schema_version: {payload.get('schema_version')!r}"
        )

    study_space = payload.get("study_space")
    if not isinstance(study_space, dict):
        raise StudySpaceImportValidationError("study_space must be an object")

    sources = _as_list(payload, "sources")
    source_chunks = _nested(sources, "chunks")
    routes = _as_list(payload, "routes")
    chapters = _as_list(payload, "chapters")
    sessions = _as_list(payload, "sessions")
    messages = _nested(sessions, "messages")
    message_citations = _nested(messages, "citations")
    quizzes = _as_list(payload, "quizzes")
    quiz_questions = _nested(quizzes, "questions")
    quiz_submissions = _nested(quizzes, "submissions")
    mastery_records = _as_list(payload, "mastery_records")
    mentor_states = _as_list(payload, "mentor_states")
    planner_states = _as_list(payload, "planner_states")
    planner_actions = _as_list(payload, "planner_actions")
    agent_runs = _as_list(payload, "agent_runs")
    notes = _as_list(payload, "notes")

    study_space_id = _required_uuid(study_space, "id", "study_space")
    source_ids = {_required_uuid(item, "id", "sources") for item in sources}
    chunk_ids = {_required_uuid(item, "id", "source_chunks") for item in source_chunks}
    route_ids = {_required_uuid(item, "id", "routes") for item in routes}
    chapter_ids = {_required_uuid(item, "id", "chapters") for item in chapters}
    session_ids = {_required_uuid(item, "id", "sessions") for item in sessions}
    message_ids = {_required_uuid(item, "id", "messages") for item in messages}
    quiz_ids = {_required_uuid(item, "id", "quizzes") for item in quizzes}
    submission_ids = {_required_uuid(item, "id", "quiz_submissions") for item in quiz_submissions}
    planner_state_ids = {_required_uuid(item, "id", "planner_states") for item in planner_states}

    for chunk in source_chunks:
        _ensure_ref(_optional_uuid(chunk, "source_id", "source_chunks"), source_ids, "source_chunks.source_id")
    for chapter in chapters:
        _ensure_ref(_optional_uuid(chapter, "learning_route_id", "chapters"), route_ids, "chapters.learning_route_id")
    for message in messages:
        _ensure_ref(_optional_uuid(message, "session_id", "messages"), session_ids, "messages.session_id")
    for citation in message_citations:
        _ensure_ref(_optional_uuid(citation, "message_id", "message_citations"), message_ids, "message_citations.message_id")
        _ensure_ref(_optional_uuid(citation, "source_id", "message_citations"), source_ids, "message_citations.source_id")
        _ensure_ref(
            _optional_uuid(citation, "source_chunk_id", "message_citations"),
            chunk_ids,
            "message_citations.source_chunk_id",
        )
    for question in quiz_questions:
        _ensure_ref(_optional_uuid(question, "quiz_id", "quiz_questions"), quiz_ids, "quiz_questions.quiz_id")
        _ensure_ref(_optional_uuid(question, "chapter_id", "quiz_questions"), chapter_ids, "quiz_questions.chapter_id")
    for submission in quiz_submissions:
        _ensure_ref(_optional_uuid(submission, "quiz_id", "quiz_submissions"), quiz_ids, "quiz_submissions.quiz_id")
        _ensure_ref(_optional_uuid(submission, "chapter_id", "quiz_submissions"), chapter_ids, "quiz_submissions.chapter_id")
    for record in mastery_records:
        _ensure_ref(_optional_uuid(record, "chapter_id", "mastery_records"), chapter_ids, "mastery_records.chapter_id")
        _ensure_ref(
            _optional_uuid(record, "last_quiz_submission_id", "mastery_records"),
            submission_ids,
            "mastery_records.last_quiz_submission_id",
        )
    for state in mentor_states:
        _ensure_ref(_optional_uuid(state, "chapter_id", "mentor_states"), chapter_ids, "mentor_states.chapter_id")
    for state in planner_states:
        _ensure_ref(_optional_uuid(state, "next_chapter_id", "planner_states"), chapter_ids, "planner_states.next_chapter_id")
    for action in planner_actions:
        _ensure_ref(_optional_uuid(action, "chapter_id", "planner_actions"), chapter_ids, "planner_actions.chapter_id")
        _ensure_ref(
            _optional_uuid(action, "source_planner_state_id", "planner_actions"),
            planner_state_ids,
            "planner_actions.source_planner_state_id",
        )
    for run in agent_runs:
        _ensure_ref(_optional_uuid(run, "session_id", "agent_runs"), session_ids, "agent_runs.session_id")
        _ensure_ref(_optional_uuid(run, "message_id", "agent_runs"), message_ids, "agent_runs.message_id")
    for note in notes:
        _ensure_ref(_optional_uuid(note, "chapter_id", "notes"), chapter_ids, "notes.chapter_id")
        _ensure_ref(_optional_uuid(note, "source_chunk_id", "notes"), chunk_ids, "notes.source_chunk_id")

    return {
        "study_space": study_space,
        "study_space_id": study_space_id,
        "sources": sources,
        "source_chunks": source_chunks,
        "routes": routes,
        "chapters": chapters,
        "sessions": sessions,
        "messages": messages,
        "message_citations": message_citations,
        "quizzes": quizzes,
        "quiz_questions": quiz_questions,
        "quiz_submissions": quiz_submissions,
        "mastery_records": mastery_records,
        "mentor_states": mentor_states,
        "planner_states": planner_states,
        "planner_actions": planner_actions,
        "agent_runs": agent_runs,
        "notes": notes,
    }


async def import_study_space(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict[str, Any],
    dry_run: bool = True,
) -> StudySpaceImportResult:
    del session
    validation = validate_study_space_import_payload(payload)
    if not dry_run:
        raise StudySpaceImportNotImplementedError(
            "Study space import restore is not implemented; call with dry_run=true to validate the payload."
        )

    summary = {
        "study_spaces": 1,
        "sources": len(validation["sources"]),
        "source_chunks": len(validation["source_chunks"]),
        "routes": len(validation["routes"]),
        "chapters": len(validation["chapters"]),
        "sessions": len(validation["sessions"]),
        "messages": len(validation["messages"]),
        "message_citations": len(validation["message_citations"]),
        "quizzes": len(validation["quizzes"]),
        "quiz_questions": len(validation["quiz_questions"]),
        "quiz_submissions": len(validation["quiz_submissions"]),
        "mastery_records": len(validation["mastery_records"]),
        "mentor_states": len(validation["mentor_states"]),
        "planner_states": len(validation["planner_states"]),
        "planner_actions": len(validation["planner_actions"]),
        "agent_runs": len(validation["agent_runs"]),
        "notes": len(validation["notes"]),
    }
    id_remap = {
        "study_spaces": {validation["study_space_id"]: str(uuid.uuid4())},
        "sources": _new_id_map(validation["sources"], "sources"),
        "source_chunks": _new_id_map(validation["source_chunks"], "source_chunks"),
        "routes": _new_id_map(validation["routes"], "routes"),
        "chapters": _new_id_map(validation["chapters"], "chapters"),
        "sessions": _new_id_map(validation["sessions"], "sessions"),
        "messages": _new_id_map(validation["messages"], "messages"),
        "message_citations": _new_id_map(validation["message_citations"], "message_citations"),
        "quizzes": _new_id_map(validation["quizzes"], "quizzes"),
        "quiz_questions": _new_id_map(validation["quiz_questions"], "quiz_questions"),
        "quiz_submissions": _new_id_map(validation["quiz_submissions"], "quiz_submissions"),
        "mastery_records": _new_id_map(validation["mastery_records"], "mastery_records"),
        "mentor_states": _new_id_map(validation["mentor_states"], "mentor_states"),
        "planner_states": _new_id_map(validation["planner_states"], "planner_states"),
        "planner_actions": _new_id_map(validation["planner_actions"], "planner_actions"),
        "agent_runs": _new_id_map(validation["agent_runs"], "agent_runs"),
        "notes": _new_id_map(validation["notes"], "notes"),
    }

    study_space = validation["study_space"]
    return StudySpaceImportResult(
        dry_run=True,
        can_restore=False,
        schema_version=EXPORT_SCHEMA_VERSION,
        original_study_space_id=validation["study_space_id"],
        summary=summary,
        tenant_rewrite={
            "from_tenant_id": study_space.get("tenant_id"),
            "to_tenant_id": str(tenant_id),
        },
        user_rewrite={
            "from_owner_user_id": study_space.get("owner_user_id"),
            "to_user_id": str(user_id),
        },
        id_remap=id_remap,
        warnings=[
            "Dry-run only: validation, tenant/user rewrite preview, and ID remap preview were computed; no rows were written."
        ],
        unsupported_write_models=RESTORE_MODEL_ORDER,
    )
