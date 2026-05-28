import uuid

from app.domain.agent_runtime.metadata import (
    SESSION_TUTOR_GRAPH_NAME,
    STATE_SCHEMA_VERSION,
    build_graph_metadata,
    session_tutor_thread_id,
)


def test_session_tutor_thread_id_is_stable() -> None:
    session_id = uuid.UUID("00000000-0000-0000-0000-000000000123")

    assert session_tutor_thread_id(session_id) == "session:00000000-0000-0000-0000-000000000123"


def test_build_graph_metadata_uses_standard_contract() -> None:
    metadata = build_graph_metadata(
        graph_name=SESSION_TUTOR_GRAPH_NAME,
        thread_id="session:abc",
        checkpoint_backend="memory",
        node_trace=["load_session_context"],
    )

    assert metadata == {
        "graph_name": "session_tutor",
        "thread_id": "session:abc",
        "checkpoint_backend": "memory",
        "state_schema_version": STATE_SCHEMA_VERSION,
        "node_trace": ["load_session_context"],
    }
