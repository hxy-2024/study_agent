import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import routes_agent_runtime
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.models import AgentRunStatus, AgentType
from app.db.session import get_db_session
from app.domain.agent_runtime.schemas import AgentRunTimelineItem, AgentRunTimelineResponse
from app.domain.agent_runtime.service import (
    _bounded_limit,
    _build_timeline_item,
    _chapter_id_from_payloads,
    _extract_graph_metadata,
    _extract_learning_signals,
    _summarize_agent_run,
)
from app.main import app


TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


async def fake_db() -> AsyncGenerator[object, None]:
    yield object()


async def fake_context() -> CurrentUserContext:
    return CurrentUserContext(user_id=USER_ID, tenant_id=TENANT_ID)


def _timeline_item(
    *,
    agent_type: str,
    study_space_id: uuid.UUID,
    chapter_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
) -> AgentRunTimelineItem:
    return AgentRunTimelineItem(
        id=uuid.uuid4(),
        agent_type=agent_type,
        status="completed",
        model="gpt-test",
        study_space_id=study_space_id,
        chapter_id=chapter_id,
        session_id=session_id,
        summary=f"{agent_type} completed.",
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
        == "Route refreshed."
    )
    assert (
        _summarize_agent_run(
            AgentType.chapter_mentor,
            AgentRunStatus.completed,
            {"summary": "Mentor state updated."},
            None,
        )
        == "Mentor state updated."
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


def test_study_space_agent_runs_uses_authorized_tenant_and_limit(monkeypatch) -> None:
    captured = {}
    study_space_id = uuid.uuid4()

    async def fake_list_agent_runs_for_study_space(**kwargs):
        captured.update(kwargs)
        return AgentRunTimelineResponse(
            runs=[
                _timeline_item(
                    agent_type="space_planner",
                    study_space_id=study_space_id,
                )
            ]
        )

    monkeypatch.setattr(
        routes_agent_runtime,
        "list_agent_runs_for_study_space",
        fake_list_agent_runs_for_study_space,
    )
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/study-spaces/{study_space_id}/agent-runs?limit=7")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == TENANT_ID
    assert captured["study_space_id"] == study_space_id
    assert captured["limit"] == 7
    assert response.json()["runs"][0]["agent_type"] == "space_planner"


def test_chapter_agent_runs_maps_value_error_to_404(monkeypatch) -> None:
    chapter_id = uuid.uuid4()

    async def fake_list_agent_runs_for_chapter(**kwargs):
        raise ValueError("Chapter not found for tenant")

    monkeypatch.setattr(
        routes_agent_runtime,
        "list_agent_runs_for_chapter",
        fake_list_agent_runs_for_chapter,
    )
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/chapters/{chapter_id}/agent-runs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Chapter not found for tenant"


def test_session_agent_runs_returns_session_tutor_run(monkeypatch) -> None:
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    session_id = uuid.uuid4()

    async def fake_list_agent_runs_for_session(**kwargs):
        return AgentRunTimelineResponse(
            runs=[
                _timeline_item(
                    agent_type="session_tutor",
                    study_space_id=study_space_id,
                    chapter_id=chapter_id,
                    session_id=session_id,
                )
            ]
        )

    monkeypatch.setattr(
        routes_agent_runtime,
        "list_agent_runs_for_session",
        fake_list_agent_runs_for_session,
    )
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/sessions/{session_id}/agent-runs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    run = response.json()["runs"][0]
    assert run["agent_type"] == "session_tutor"
    assert run["session_id"] == str(session_id)
