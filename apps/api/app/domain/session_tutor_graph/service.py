import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chapter_mentor.providers import AnswerProvider
from app.domain.rag.embeddings import EmbeddingProvider
from app.domain.sessions.schemas import MessageCitationResponse, MessageResponse
from app.domain.session_tutor_graph.graph import build_session_tutor_graph
from app.domain.session_tutor_graph.state import (
    MessageResponsePayload,
    SessionTutorGraphState,
)


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


async def run_session_tutor_graph(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    embedding_provider: EmbeddingProvider,
    answer_provider: AnswerProvider,
) -> MessageResponse:
    graph = build_session_tutor_graph(
        db_session=session,
        embedding_provider=embedding_provider,
        answer_provider=answer_provider,
    )
    initial_state = SessionTutorGraphState(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        session_id=str(session_id),
        content=content,
        node_trace=[],
        learning_signals=[],
    )
    final_state = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": f"session:{session_id}"}},
    )
    return _build_message_response(final_state["assistant_response"])
