import uuid

import pytest

from app.domain.study_spaces.export import EXPORT_SCHEMA_VERSION
from app.domain.study_spaces.import_restore import (
    StudySpaceImportNotImplementedError,
    StudySpaceImportValidationError,
    import_study_space,
    validate_study_space_import_payload,
)


def _payload() -> dict:
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    route_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    session_id = uuid.uuid4()
    message_id = uuid.uuid4()
    quiz_id = uuid.uuid4()
    submission_id = uuid.uuid4()
    planner_state_id = uuid.uuid4()
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "study_space": {
            "id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "owner_user_id": str(uuid.uuid4()),
            "name": "Import me",
            "goal": "Validate import",
        },
        "sources": [{"id": str(source_id), "chunks": [{"id": str(chunk_id), "source_id": str(source_id)}]}],
        "routes": [{"id": str(route_id)}],
        "chapters": [{"id": str(chapter_id), "learning_route_id": str(route_id)}],
        "sessions": [
            {
                "id": str(session_id),
                "chapter_id": str(chapter_id),
                "messages": [
                    {
                        "id": str(message_id),
                        "session_id": str(session_id),
                        "citations": [
                            {
                                "id": str(uuid.uuid4()),
                                "message_id": str(message_id),
                                "source_id": str(source_id),
                                "source_chunk_id": str(chunk_id),
                            }
                        ],
                    }
                ],
            }
        ],
        "quizzes": [
            {
                "id": str(quiz_id),
                "chapter_id": str(chapter_id),
                "questions": [{"id": str(uuid.uuid4()), "quiz_id": str(quiz_id), "chapter_id": str(chapter_id)}],
                "submissions": [
                    {
                        "id": str(submission_id),
                        "quiz_id": str(quiz_id),
                        "chapter_id": str(chapter_id),
                        "user_id": str(uuid.uuid4()),
                    }
                ],
            }
        ],
        "mastery_records": [
            {
                "id": str(uuid.uuid4()),
                "chapter_id": str(chapter_id),
                "user_id": str(uuid.uuid4()),
                "last_quiz_submission_id": str(submission_id),
            }
        ],
        "mentor_states": [{"id": str(uuid.uuid4()), "chapter_id": str(chapter_id)}],
        "planner_states": [{"id": str(planner_state_id), "user_id": str(uuid.uuid4()), "next_chapter_id": str(chapter_id)}],
        "planner_actions": [
            {
                "id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "chapter_id": str(chapter_id),
                "source_planner_state_id": str(planner_state_id),
            }
        ],
        "agent_runs": [{"id": str(uuid.uuid4()), "session_id": str(session_id), "message_id": str(message_id)}],
        "notes": [{"id": str(uuid.uuid4()), "chapter_id": str(chapter_id), "source_chunk_id": str(chunk_id)}],
    }


def test_validate_import_payload_requires_supported_schema_version() -> None:
    payload = _payload()
    payload["schema_version"] = 999

    with pytest.raises(StudySpaceImportValidationError, match="Unsupported study space export schema_version"):
        validate_study_space_import_payload(payload)


async def test_import_study_space_dry_run_returns_summary_rewrite_and_id_remap() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    result = await import_study_space(
        session=object(),
        tenant_id=tenant_id,
        user_id=user_id,
        payload=_payload(),
        dry_run=True,
    )

    assert result.dry_run is True
    assert result.can_restore is False
    assert result.schema_version == EXPORT_SCHEMA_VERSION
    assert result.summary["study_spaces"] == 1
    assert result.summary["sources"] == 1
    assert result.summary["source_chunks"] == 1
    assert result.summary["messages"] == 1
    assert result.summary["message_citations"] == 1
    assert result.summary["quiz_questions"] == 1
    assert result.summary["quiz_submissions"] == 1
    assert result.summary["mastery_records"] == 1
    assert result.tenant_rewrite["to_tenant_id"] == str(tenant_id)
    assert result.user_rewrite["to_user_id"] == str(user_id)
    assert result.id_remap["study_spaces"][result.original_study_space_id] != result.original_study_space_id


async def test_import_study_space_non_dry_run_is_explicitly_not_implemented() -> None:
    with pytest.raises(StudySpaceImportNotImplementedError, match="not implemented"):
        await import_study_space(
            session=object(),
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            payload=_payload(),
            dry_run=False,
        )
