import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.db.models import AgentRunStatus, AgentType
from app.domain.agent_runtime.service import (
    _bounded_limit,
    _build_timeline_item,
    _chapter_id_from_payloads,
    _extract_graph_metadata,
    _extract_learning_signals,
    _summarize_agent_run,
)


def test_extract_graph_metadata_prefers_output_payload_and_sanitizes_node_trace() -> None:
    metadata = _extract_graph_metadata(
        input_payload={
            "graph_name": "input_graph",
            "thread_id": "input-thread",
            "checkpoint_backend": "memory",
            "state_schema_version": 1,
            "node_trace": ["input"],
        },
        output_payload={
            "graph_name": "output_graph",
            "thread_id": "output-thread",
            "checkpoint_backend": "postgres",
            "state_schema_version": 2,
            "node_trace": "not-a-list",
        },
    )

    assert metadata.graph_name == "output_graph"
    assert metadata.thread_id == "output-thread"
    assert metadata.checkpoint_backend == "postgres"
    assert metadata.state_schema_version == 2
    assert metadata.node_trace == []


def test_extract_graph_metadata_falls_back_to_input_payload() -> None:
    metadata = _extract_graph_metadata(
        input_payload={"graph_name": "session_tutor", "node_trace": ["load", 123]},
        output_payload={},
    )

    assert metadata.graph_name == "session_tutor"
    assert metadata.node_trace == ["load", "123"]


def test_extract_learning_signals_keeps_only_dict_items() -> None:
    signals = _extract_learning_signals(
        {
            "learning_signals": [
                {"type": "needs_review", "value": True},
                "bad",
                None,
                {"type": "evidence_used", "value": False},
            ]
        }
    )

    assert signals == [
        {"type": "needs_review", "value": True},
        {"type": "evidence_used", "value": False},
    ]


def test_chapter_id_from_payloads_prefers_output_and_ignores_invalid_values() -> None:
    input_chapter_id = uuid.uuid4()
    output_chapter_id = uuid.uuid4()

    assert _chapter_id_from_payloads(
        {"chapter_id": str(input_chapter_id)},
        {"chapter_id": str(output_chapter_id)},
    ) == output_chapter_id
    assert _chapter_id_from_payloads({"chapter_id": "not-a-uuid"}, {}) is None


def test_summarize_agent_run_uses_stable_agent_summaries() -> None:
    assert (
        _summarize_agent_run(
            AgentType.space_planner,
            AgentRunStatus.completed,
            {"summary": "Route refreshed."},
            None,
        )
        == "Space planner completed: Route refreshed."
    )
    assert (
        _summarize_agent_run(
            AgentType.chapter_mentor,
            AgentRunStatus.completed,
            {"summary": "Mentor state updated."},
            None,
        )
        == "Chapter mentor completed: Mentor state updated."
    )
    assert (
        _summarize_agent_run(
            AgentType.session_tutor,
            AgentRunStatus.completed,
            {"citation_count": 3},
            None,
        )
        == "Session tutor completed with 3 citations."
    )
    assert (
        _summarize_agent_run(
            AgentType.session_tutor,
            AgentRunStatus.failed,
            {},
            "provider unavailable",
        )
        == "Run failed: provider unavailable"
    )


def test_build_timeline_item_uses_session_chapter_id_over_payload_chapter_id() -> None:
    run_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    session_id = uuid.uuid4()
    message_id = uuid.uuid4()
    session_chapter_id = uuid.uuid4()
    payload_chapter_id = uuid.uuid4()
    created_at = datetime.now(UTC)

    fake_run = SimpleNamespace(
        id=run_id,
        agent_type=AgentType.session_tutor,
        status=AgentRunStatus.completed,
        model="gpt-test",
        study_space_id=study_space_id,
        session_id=session_id,
        message_id=message_id,
        input_payload={"chapter_id": str(payload_chapter_id)},
        output_payload={
            "graph_name": "session_tutor",
            "thread_id": "session-thread",
            "checkpoint_backend": "memory",
            "state_schema_version": 1,
            "node_trace": ["load_context"],
            "learning_signals": [{"type": "needs_review"}],
            "citation_count": 1,
        },
        error_message=None,
        created_at=created_at,
    )

    item = _build_timeline_item(fake_run, chapter_id=session_chapter_id)

    assert item.id == run_id
    assert item.agent_type == "session_tutor"
    assert item.status == "completed"
    assert item.chapter_id == session_chapter_id
    assert item.session_id == session_id
    assert item.message_id == message_id
    assert item.graph_name == "session_tutor"
    assert item.thread_id == "session-thread"
    assert item.node_trace == ["load_context"]
    assert item.learning_signals == [{"type": "needs_review"}]
    assert item.summary == "Session tutor completed with 1 citation."
    assert item.created_at == created_at


def test_bounded_limit_clamps_to_supported_range() -> None:
    assert _bounded_limit(0) == 1
    assert _bounded_limit(20) == 20
    assert _bounded_limit(250) == 100
