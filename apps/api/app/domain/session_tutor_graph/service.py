import logging
import uuid
from datetime import datetime
from typing import Awaitable, Callable

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRunStatus
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
        await record_agent_run(
            session=session,
            tenant_id=tenant_id,
            session_id=session_id,
            input_payload={
                "content": content,
                "user_message_id": user_message_id,
                "node_trace": state.get("node_trace", []),
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
) -> MessageResponse:
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
    graph_builder.add_node(
        "record_agent_run",
        observed_async(
            lambda state: nodes.record_graph_agent_run(state, db_session=session),
        ),
    )
    graph_builder.set_entry_point("load_session_context")
    graph_builder.add_edge("load_session_context", "persist_user_message")
    graph_builder.add_edge("persist_user_message", "load_chapter_supervision")
    graph_builder.add_edge("load_chapter_supervision", "retrieve_evidence")
    graph_builder.add_edge("retrieve_evidence", "generate_answer")
    graph_builder.add_edge("generate_answer", "persist_assistant_message")
    graph_builder.add_edge("persist_assistant_message", "extract_learning_signals")
    graph_builder.add_edge("extract_learning_signals", "record_agent_run")
    graph_builder.add_edge("record_agent_run", END)
    graph = graph_builder.compile()

    try:
        final_state = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": f"session:{session_id}"}},
        )
    except Exception as exc:
        await _try_record_failed_agent_run(
            session=session,
            tenant_id=tenant_id,
            session_id=session_id,
            content=content,
            state=latest_state,
            exc=exc,
        )
        raise
    return _build_message_response(final_state["assistant_response"])
