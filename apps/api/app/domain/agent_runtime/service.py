import uuid
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, AgentRunStatus, AgentType, Chapter, Session, StudySpace
from app.domain.agent_runtime.schemas import (
    AgentRunGraphMetadata,
    AgentRunTimelineItem,
    AgentRunTimelineResponse,
)


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _safe_payload(payload: Any) -> dict:
    return payload if isinstance(payload, dict) else {}


def _bounded_limit(limit: int) -> int:
    return max(1, min(limit, 100))


def _extract_graph_metadata(input_payload: Any, output_payload: Any) -> AgentRunGraphMetadata:
    input_data = _safe_payload(input_payload)
    output_data = _safe_payload(output_payload)
    graph_keys = {
        "graph_name",
        "thread_id",
        "checkpoint_backend",
        "state_schema_version",
        "node_trace",
    }
    payload = output_data if any(key in output_data for key in graph_keys) else input_data

    raw_node_trace = payload.get("node_trace")
    node_trace = [str(item) for item in raw_node_trace] if isinstance(raw_node_trace, list) else []
    raw_state_schema_version = payload.get("state_schema_version")
    state_schema_version = (
        raw_state_schema_version if isinstance(raw_state_schema_version, int) else None
    )

    raw_graph_name = payload.get("graph_name")
    raw_thread_id = payload.get("thread_id")
    raw_checkpoint_backend = payload.get("checkpoint_backend")

    return AgentRunGraphMetadata(
        graph_name=raw_graph_name if isinstance(raw_graph_name, str) else None,
        thread_id=raw_thread_id if isinstance(raw_thread_id, str) else None,
        checkpoint_backend=(
            raw_checkpoint_backend if isinstance(raw_checkpoint_backend, str) else None
        ),
        state_schema_version=state_schema_version,
        node_trace=node_trace,
    )


def _extract_learning_signals(output_payload: Any) -> list[dict]:
    raw_signals = _safe_payload(output_payload).get("learning_signals")
    if not isinstance(raw_signals, list):
        return []
    return [signal for signal in raw_signals if isinstance(signal, dict)]


def _summarize_agent_run(
    agent_type: AgentType | str,
    status: AgentRunStatus | str,
    output_payload: Any,
    error_message: str | None,
) -> str:
    if _enum_value(status) == AgentRunStatus.failed.value:
        return f"Run failed: {error_message or 'unknown error'}"

    output_data = _safe_payload(output_payload)
    summary = output_data.get("summary")
    summary_text = summary if isinstance(summary, str) and summary else None
    agent_type_value = _enum_value(agent_type)

    if agent_type_value == AgentType.space_planner.value:
        return summary_text or "Space planner updated next action."
    if agent_type_value == AgentType.chapter_mentor.value:
        return summary_text or "Chapter mentor state refreshed."
    if agent_type_value == AgentType.session_tutor.value:
        raw_citation_count = output_data.get("citation_count", 0)
        citation_count = raw_citation_count if isinstance(raw_citation_count, int) else 0
        noun = "citation" if citation_count == 1 else "citations"
        return f"Session tutor completed with {citation_count} {noun}."
    return f"{agent_type_value} run {_enum_value(status)}."


def _chapter_id_from_payloads(input_payload: Any, output_payload: Any) -> uuid.UUID | None:
    for payload in (_safe_payload(output_payload), _safe_payload(input_payload)):
        raw_chapter_id = payload.get("chapter_id")
        if raw_chapter_id is None:
            continue
        try:
            return uuid.UUID(str(raw_chapter_id))
        except ValueError:
            continue
    return None


def _build_timeline_item(
    row: AgentRun,
    chapter_id: uuid.UUID | None = None,
) -> AgentRunTimelineItem:
    metadata = _extract_graph_metadata(row.input_payload, row.output_payload)
    resolved_chapter_id = chapter_id or _chapter_id_from_payloads(
        row.input_payload,
        row.output_payload,
    )
    summary = _summarize_agent_run(
        row.agent_type,
        row.status,
        row.output_payload,
        row.error_message,
    )

    return AgentRunTimelineItem(
        id=row.id,
        agent_type=_enum_value(row.agent_type),
        status=_enum_value(row.status),
        model=row.model,
        study_space_id=row.study_space_id,
        chapter_id=resolved_chapter_id,
        session_id=row.session_id,
        message_id=row.message_id,
        graph_name=metadata.graph_name,
        thread_id=metadata.thread_id,
        checkpoint_backend=metadata.checkpoint_backend,
        state_schema_version=metadata.state_schema_version,
        node_trace=metadata.node_trace,
        learning_signals=_extract_learning_signals(row.output_payload),
        summary=summary,
        error_message=row.error_message,
        created_at=row.created_at,
    )


async def list_agent_runs_for_study_space(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    limit: int = 20,
) -> AgentRunTimelineResponse:
    study_space = await session.scalar(
        select(StudySpace).where(
            StudySpace.id == study_space_id,
            StudySpace.tenant_id == tenant_id,
        )
    )
    if study_space is None:
        raise ValueError("Study space not found for tenant")

    rows = list(
        await session.scalars(
            select(AgentRun)
            .where(
                AgentRun.tenant_id == tenant_id,
                AgentRun.study_space_id == study_space_id,
            )
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .limit(_bounded_limit(limit))
        )
    )
    chapter_ids_by_session = await _session_chapter_ids(
        session=session,
        tenant_id=tenant_id,
        session_ids=[row.session_id for row in rows if row.session_id is not None],
    )
    return AgentRunTimelineResponse(
        runs=[
            _build_timeline_item(row, chapter_id=chapter_ids_by_session.get(row.session_id))
            for row in rows
        ]
    )


async def list_agent_runs_for_chapter(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
    limit: int = 20,
) -> AgentRunTimelineResponse:
    chapter = await session.scalar(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.tenant_id == tenant_id,
        )
    )
    if chapter is None:
        raise ValueError("Chapter not found for tenant")

    chapter_id_text = str(chapter_id)
    payload_chapter_matches = or_(
        AgentRun.output_payload["chapter_id"].as_string() == chapter_id_text,
        AgentRun.input_payload["chapter_id"].as_string() == chapter_id_text,
    )
    rows = list(
        await session.scalars(
            select(AgentRun)
            .outerjoin(Session, AgentRun.session_id == Session.id)
            .where(
                AgentRun.tenant_id == tenant_id,
                AgentRun.study_space_id == chapter.study_space_id,
                or_(
                    and_(
                        AgentRun.agent_type == AgentType.session_tutor,
                        Session.tenant_id == tenant_id,
                        Session.chapter_id == chapter_id,
                    ),
                    and_(
                        AgentRun.agent_type.in_(
                            [AgentType.chapter_mentor, AgentType.space_planner]
                        ),
                        payload_chapter_matches,
                    ),
                ),
            )
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .limit(_bounded_limit(limit))
        )
    )
    chapter_ids_by_session = await _session_chapter_ids(
        session=session,
        tenant_id=tenant_id,
        session_ids=[row.session_id for row in rows if row.session_id is not None],
    )
    return AgentRunTimelineResponse(
        runs=[
            _build_timeline_item(
                row,
                chapter_id=chapter_ids_by_session.get(row.session_id, chapter_id),
            )
            for row in rows
        ]
    )


async def list_agent_runs_for_session(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    limit: int = 20,
) -> AgentRunTimelineResponse:
    tutor_session = await session.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.tenant_id == tenant_id,
        )
    )
    if tutor_session is None:
        raise ValueError("Session not found for tenant")

    rows = list(
        await session.scalars(
            select(AgentRun)
            .where(
                AgentRun.tenant_id == tenant_id,
                AgentRun.session_id == session_id,
            )
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .limit(_bounded_limit(limit))
        )
    )
    return AgentRunTimelineResponse(
        runs=[_build_timeline_item(row, chapter_id=tutor_session.chapter_id) for row in rows]
    )


async def _session_chapter_ids(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_ids: list[uuid.UUID],
) -> dict[uuid.UUID, uuid.UUID]:
    if not session_ids:
        return {}

    session_rows = await session.scalars(
        select(Session).where(
            Session.tenant_id == tenant_id,
            Session.id.in_(session_ids),
        )
    )
    return {row.id: row.chapter_id for row in session_rows}
