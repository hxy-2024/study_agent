from app.db.models import (
    AgentRun,
    AgentRunStatus,
    AgentType,
    Message,
    MessageCitation,
    MessageRole,
    Session,
    SessionStatus,
)


def test_session_tutor_models_have_expected_tables() -> None:
    assert Session.__tablename__ == "sessions"
    assert Message.__tablename__ == "messages"
    assert MessageCitation.__tablename__ == "message_citations"
    assert AgentRun.__tablename__ == "agent_runs"


def test_session_tutor_enums_have_expected_values() -> None:
    assert SessionStatus.active.value == "active"
    assert SessionStatus.archived.value == "archived"
    assert MessageRole.user.value == "user"
    assert MessageRole.assistant.value == "assistant"
    assert AgentType.session_tutor.value == "session_tutor"
    assert AgentRunStatus.pending.value == "pending"
    assert AgentRunStatus.completed.value == "completed"
    assert AgentRunStatus.failed.value == "failed"


def test_session_tutor_tables_are_tenant_and_context_scoped() -> None:
    assert "tenant_id" in Session.__table__.columns
    assert "study_space_id" in Session.__table__.columns
    assert "chapter_id" in Session.__table__.columns
    assert "tenant_id" in Message.__table__.columns
    assert "session_id" in Message.__table__.columns
    assert "source_chunk_id" in MessageCitation.__table__.columns
    assert "input_payload" in AgentRun.__table__.columns
    assert "output_payload" in AgentRun.__table__.columns
