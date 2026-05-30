import logging
import uuid
from datetime import datetime
from typing import Awaitable, Callable

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import AgentRunStatus
from app.domain.agent_runtime.checkpoints import create_checkpointer
from app.domain.agent_runtime.config import graph_runtime_config_from_settings
from app.domain.agent_runtime.metadata import (
    SESSION_TUTOR_GRAPH_NAME,
    build_graph_metadata,
    session_tutor_thread_id,
)
from app.domain.chapter_mentor.providers import AnswerProvider
from app.domain.rag.embeddings import EmbeddingProvider
from app.domain.sessions.schemas import MessageCitationResponse, MessageResponse
from app.domain.sessions.service import record_agent_run
from app.domain.session_tutor_graph import nodes
from app.domain.session_tutor_graph.state import (
    MessageResponsePayload,
    SessionTutorGraphState,
)

LOGGER = logging.getLogger(__name__)


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _build_message_response(payload: MessageResponsePayload) -> MessageResponse:
    return MessageResponse(
        id=uuid.UUID(payload["id"]),
        session_id=uuid.UUID(payload["session_id"]),
        role=payload["role"],
        content=payload["content"],
        metadata=payload["metadata"],
        citations=[
            MessageCitationResponse(
                id=uuid.UUID(citation["id"]),
                message_id=uuid.UUID(citation["message_id"]),
                source_id=uuid.UUID(citation["source_id"]),
                source_chunk_id=uuid.UUID(citation["source_chunk_id"]),
                chunk_id=uuid.UUID(citation["chunk_id"]),
                source_jump=citation["source_jump"],
                source_filename=citation["source_filename"],
                chunk_index=citation["chunk_index"],
                text=citation["text"],
                quote=citation["quote"],
                citation=citation["citation"],
            )
            for citation in payload["citations"]
        ],
        created_at=_parse_datetime(payload["created_at"]),
    )


async def _try_record_failed_agent_run(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    state: SessionTutorGraphState,
    thread_id: str,
    checkpoint_backend: str,
    exc: Exception,
) -> None:
    user_message_id = state.get("user_message_id")
    if user_message_id is None:
        return

    rollback = getattr(session, "rollback", None)
    if rollback is not None:
        try:
            await rollback()
        except Exception:
            LOGGER.exception("Failed to roll back before recording graph failure")

    try:
        metadata = build_graph_metadata(
            graph_name=SESSION_TUTOR_GRAPH_NAME,
            thread_id=thread_id,
            checkpoint_backend=checkpoint_backend,
            node_trace=state.get("node_trace", []),
        )
        await record_agent_run(
            session=session,
            tenant_id=tenant_id,
            session_id=session_id,
            input_payload={
                **metadata,
                "content": content,
                "user_message_id": user_message_id,
            },
            output_payload={},
            model="langgraph:deterministic",
            status=AgentRunStatus.failed,
            error_message=str(exc),
        )
    except Exception:
        LOGGER.exception("Failed to record session tutor graph failure")


async def run_session_tutor_graph(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    embedding_provider: EmbeddingProvider,
    answer_provider: AnswerProvider,
    web_search_enabled: bool | None = None,
) -> MessageResponse:
    settings = get_settings()
    effective_web_search_enabled = (
        settings.session_tutor_web_search_enabled
        if web_search_enabled is None
        else web_search_enabled
    )
    runtime_config = graph_runtime_config_from_settings(settings)
    thread_id = session_tutor_thread_id(session_id)
    checkpointer = create_checkpointer(runtime_config)
    initial_state = SessionTutorGraphState(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        session_id=str(session_id),
        content=content,
        node_trace=[],
        learning_signals=[],
    )
    latest_state = initial_state.copy()

    def remember(state: SessionTutorGraphState) -> None:
        latest_state.clear()
        latest_state.update(state)

    def observed_async(
        node: Callable[[SessionTutorGraphState], Awaitable[SessionTutorGraphState]],
    ) -> Callable[[SessionTutorGraphState], Awaitable[SessionTutorGraphState]]:
        async def wrapper(state: SessionTutorGraphState) -> SessionTutorGraphState:
            try:
                result = await node(state)
            except Exception:
                remember(state)
                raise
            remember(result)
            return result

        return wrapper

    def observed_sync(
        node: Callable[[SessionTutorGraphState], SessionTutorGraphState],
    ) -> Callable[[SessionTutorGraphState], SessionTutorGraphState]:
        def wrapper(state: SessionTutorGraphState) -> SessionTutorGraphState:
            try:
                result = node(state)
            except Exception:
                remember(state)
                raise
            remember(result)
            return result

        return wrapper

    graph_builder = StateGraph(SessionTutorGraphState)
    graph_builder.add_node(
        "load_session_context",
        observed_async(
            lambda state: nodes.load_session_context(state, db_session=session),
        ),
    )
    graph_builder.add_node(
        "persist_user_message",
        observed_async(
            lambda state: nodes.persist_user_message(state, db_session=session),
        ),
    )
    graph_builder.add_node(
        "load_chapter_supervision",
        observed_async(
            lambda state: nodes.load_chapter_supervision(state, db_session=session),
        ),
    )
    graph_builder.add_node(
        "retrieve_evidence",
        observed_async(
            lambda state: nodes.retrieve_evidence(
                state,
                db_session=session,
                embedding_provider=embedding_provider,
            ),
        ),
    )
    graph_builder.add_node(
        "web_search",
        observed_async(
            lambda state: nodes.web_search(
                state,
                enabled=effective_web_search_enabled,
                max_results=settings.session_tutor_web_search_max_results,
                timeout_seconds=settings.session_tutor_web_search_timeout_seconds,
            ),
        ),
    )
    graph_builder.add_node(
        "generate_answer",
        observed_async(
            lambda state: nodes.generate_answer(
                state,
                answer_provider=answer_provider,
            ),
        ),
    )
    graph_builder.add_node(
        "persist_assistant_message",
        observed_async(
            lambda state: nodes.persist_assistant_message(state, db_session=session),
        ),
    )
    graph_builder.add_node(
        "extract_learning_signals",
        observed_sync(nodes.extract_learning_signals),
    )

    async def record_graph_agent_run(
        state: SessionTutorGraphState,
    ) -> SessionTutorGraphState:
        state.setdefault("node_trace", []).append("record_agent_run")
        assistant_message_id = state.get("assistant_message_id")
        metadata = build_graph_metadata(
            graph_name=SESSION_TUTOR_GRAPH_NAME,
            thread_id=thread_id,
            checkpoint_backend=runtime_config.checkpoint_backend,
            node_trace=state["node_trace"],
        )
        await record_agent_run(
            session=session,
            tenant_id=tenant_id,
            session_id=session_id,
            message_id=uuid.UUID(assistant_message_id) if assistant_message_id else None,
            input_payload={
                "content": state["content"],
                "user_message_id": str(state.get("user_message_id")),
                "chapter_supervision_used": state.get("chapter_supervision") is not None,
                "graph_enabled": runtime_config.session_tutor_graph_enabled,
                "checkpoint_backend": runtime_config.checkpoint_backend,
                "web_search_enabled": effective_web_search_enabled,
            },
            output_payload={
                **metadata,
                "assistant_message_id": str(state.get("assistant_message_id")),
                "citation_count": len(state.get("citations", [])),
                "web_search_result_count": len(state.get("web_search_results", [])),
                "web_search_error": state.get("web_search_error"),
                "learning_signals": state["learning_signals"],
                "chapter_supervision_used": state.get("chapter_supervision") is not None,
                "graph_enabled": runtime_config.session_tutor_graph_enabled,
            },
            model="langgraph:deterministic",
            status=AgentRunStatus.completed,
        )
        return state

    graph_builder.add_node(
        "record_agent_run",
        observed_async(record_graph_agent_run),
    )
    graph_builder.set_entry_point("load_session_context")
    graph_builder.add_edge("load_session_context", "persist_user_message")
    graph_builder.add_edge("persist_user_message", "load_chapter_supervision")
    graph_builder.add_edge("load_chapter_supervision", "retrieve_evidence")
    graph_builder.add_edge("retrieve_evidence", "web_search")
    graph_builder.add_edge("web_search", "generate_answer")
    graph_builder.add_edge("generate_answer", "persist_assistant_message")
    graph_builder.add_edge("persist_assistant_message", "extract_learning_signals")
    graph_builder.add_edge("extract_learning_signals", "record_agent_run")
    graph_builder.add_edge("record_agent_run", END)
    graph = graph_builder.compile(checkpointer=checkpointer)

    try:
        final_state = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:
        await _try_record_failed_agent_run(
            session=session,
            tenant_id=tenant_id,
            session_id=session_id,
            content=content,
            state=latest_state,
            thread_id=thread_id,
            checkpoint_backend=runtime_config.checkpoint_backend,
            exc=exc,
        )
        raise
    return _build_message_response(final_state["assistant_response"])
