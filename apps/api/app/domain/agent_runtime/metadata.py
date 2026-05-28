import uuid
from typing import TypedDict

from app.domain.agent_runtime.config import CheckpointBackend


SESSION_TUTOR_GRAPH_NAME = "session_tutor"
STATE_SCHEMA_VERSION = 1


class GraphRunMetadata(TypedDict):
    graph_name: str
    thread_id: str
    checkpoint_backend: CheckpointBackend
    state_schema_version: int
    node_trace: list[str]


def session_tutor_thread_id(session_id: uuid.UUID | str) -> str:
    return f"session:{session_id}"


def build_graph_metadata(
    graph_name: str,
    thread_id: str,
    checkpoint_backend: CheckpointBackend,
    node_trace: list[str],
) -> GraphRunMetadata:
    return {
        "graph_name": graph_name,
        "thread_id": thread_id,
        "checkpoint_backend": checkpoint_backend,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "node_trace": list(node_trace),
    }
