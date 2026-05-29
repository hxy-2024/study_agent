import uuid
from datetime import datetime

from app.db.models import AgentRunStatus, MessageRole
from app.domain.chapter_mentor.service import load_source_filenames
from app.domain.chapter_mentor_state.service import get_chapter_mentor_state
from app.domain.rag.retrieval import RetrievedChunk, retrieve_chunks
from app.domain.sessions.schemas import MessageCitationCreate, MessageCreate
from app.domain.sessions.service import (
    create_message,
    create_message_with_response,
    ensure_session_in_tenant,
    record_agent_run,
)
from app.domain.session_tutor_graph.state import (
    AnswerCitation,
    ChapterSupervision,
    MessageCitationPayload,
    MessageResponsePayload,
    RetrievedEvidence,
    SessionTutorGraphState,
    WebSearchResult,
    build_learning_signals,
)
from app.domain.session_tutor_graph.tools import web_search_tool


def _trace(state: SessionTutorGraphState, node_name: str) -> None:
    state.setdefault("node_trace", []).append(node_name)


def _isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _source_filenames_by_uuid(state: SessionTutorGraphState) -> dict[uuid.UUID, str]:
    return {
        uuid.UUID(source_id): filename
        for source_id, filename in state.get("source_filenames", {}).items()
    }


def _chunk_by_id(chunks: list[RetrievedChunk]) -> dict[uuid.UUID, RetrievedChunk]:
    return {chunk.id: chunk for chunk in chunks}


def _citation_score(citation_chunk_id: uuid.UUID, chunks: list[RetrievedChunk]) -> float:
    chunk = _chunk_by_id(chunks).get(citation_chunk_id)
    return chunk.score if chunk is not None else 0.0


def _retrieved_chunks_from_state(state: SessionTutorGraphState) -> list[RetrievedChunk]:
    source_filenames = state.get("source_filenames", {})
    return [
        RetrievedChunk(
            id=uuid.UUID(evidence["chunk_id"]),
            tenant_id=uuid.UUID(state["tenant_id"]),
            study_space_id=uuid.UUID(state["study_space_id"]),
            source_id=uuid.UUID(evidence["source_id"]),
            chunk_index=evidence["chunk_index"],
            text=evidence["text"],
            citation={
                "source_filename": source_filenames.get(
                    str(evidence["source_id"]),
                    "Unknown source",
                ),
                "chunk_index": evidence["chunk_index"],
            },
            embedding=[],
            score=evidence["score"],
        )
        for evidence in state.get("retrieved_chunks", [])
    ]


async def load_session_context(
    state: SessionTutorGraphState,
    *,
    db_session,
) -> SessionTutorGraphState:
    _trace(state, "load_session_context")
    tutor_session = await ensure_session_in_tenant(
        session=db_session,
        tenant_id=uuid.UUID(state["tenant_id"]),
        session_id=uuid.UUID(state["session_id"]),
    )
    state["study_space_id"] = str(tutor_session.study_space_id)
    state["chapter_id"] = str(tutor_session.chapter_id)
    return state


async def persist_user_message(
    state: SessionTutorGraphState,
    *,
    db_session,
) -> SessionTutorGraphState:
    _trace(state, "persist_user_message")
    message = await create_message(
        session=db_session,
        tenant_id=uuid.UUID(state["tenant_id"]),
        session_id=uuid.UUID(state["session_id"]),
        payload=MessageCreate(role=MessageRole.user, content=state["content"]),
    )
    state["user_message_id"] = str(message.id)
    return state


async def load_chapter_supervision(
    state: SessionTutorGraphState,
    *,
    db_session,
) -> SessionTutorGraphState:
    _trace(state, "load_chapter_supervision")
    mentor_state = await get_chapter_mentor_state(
        session=db_session,
        tenant_id=uuid.UUID(state["tenant_id"]),
        chapter_id=uuid.UUID(state["chapter_id"]),
    )
    state["chapter_supervision"] = (
        ChapterSupervision(
            summary=mentor_state.summary,
            weak_points=mentor_state.weak_points or [],
            next_actions=mentor_state.next_actions or [],
        )
        if mentor_state is not None
        else None
    )
    return state


async def retrieve_evidence(
    state: SessionTutorGraphState,
    *,
    db_session,
    embedding_provider,
) -> SessionTutorGraphState:
    _trace(state, "retrieve_evidence")
    chunks = await retrieve_chunks(
        session=db_session,
        tenant_id=uuid.UUID(state["tenant_id"]),
        study_space_id=uuid.UUID(state["study_space_id"]),
        query=state["content"],
        limit=5,
        embedding_provider=embedding_provider,
    )
    source_filenames = await load_source_filenames(
        session=db_session,
        tenant_id=uuid.UUID(state["tenant_id"]),
        study_space_id=uuid.UUID(state["study_space_id"]),
        source_ids=[chunk.source_id for chunk in chunks],
    )
    state["retrieved_chunks"] = [
        RetrievedEvidence(
            source_id=str(chunk.source_id),
            chunk_id=str(chunk.id),
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            score=chunk.score,
        )
        for chunk in chunks
    ]
    state["source_filenames"] = {
        str(source_id): filename for source_id, filename in source_filenames.items()
    }
    return state


async def generate_answer(
    state: SessionTutorGraphState,
    *,
    answer_provider,
) -> SessionTutorGraphState:
    _trace(state, "generate_answer")
    chunks = _retrieved_chunks_from_state(state)
    answer = await answer_provider.answer(
        question=state["content"],
        chunks=chunks,
        source_filenames=_source_filenames_by_uuid(state),
        web_search_results=state.get("web_search_results", []),
    )
    state["answer"] = answer.answer
    state["citations"] = [
        AnswerCitation(
            source_id=str(citation.source_id),
            chunk_id=str(citation.chunk_id),
            source_filename=citation.source_filename,
            chunk_index=citation.chunk_index,
            text=citation.text,
            score=_citation_score(citation.chunk_id, chunks),
        )
        for citation in answer.citations
    ]
    return state


async def web_search(
    state: SessionTutorGraphState,
    *,
    enabled: bool,
    max_results: int,
    timeout_seconds: int,
) -> SessionTutorGraphState:
    _trace(state, "web_search")
    if not enabled:
        state["web_search_results"] = []
        return state

    try:
        result = await web_search_tool.ainvoke(
            {
                "query": state["content"],
                "max_results": max_results,
                "timeout_seconds": timeout_seconds,
            }
        )
    except Exception as exc:
        state["web_search_results"] = []
        state["web_search_error"] = str(exc)
        return state

    state["web_search_results"] = [
        WebSearchResult(
            title=str(item.get("title", "")),
            url=str(item.get("url", "")),
            snippet=str(item.get("snippet", "")),
        )
        for item in result
        if isinstance(item, dict)
    ]
    return state


def _message_response_payload(response) -> MessageResponsePayload:
    return MessageResponsePayload(
        id=str(response.id),
        session_id=str(response.session_id),
        role=response.role,
        content=response.content,
        metadata=response.metadata,
        citations=[
            MessageCitationPayload(
                id=str(citation.id),
                message_id=str(citation.message_id),
                source_id=str(citation.source_id),
                source_chunk_id=str(citation.source_chunk_id),
                chunk_id=str(citation.chunk_id),
                source_filename=citation.source_filename,
                chunk_index=citation.chunk_index,
                text=citation.text,
                quote=citation.quote,
                citation=citation.citation,
            )
            for citation in response.citations
        ],
        created_at=_isoformat_or_none(response.created_at),
    )


async def persist_assistant_message(
    state: SessionTutorGraphState,
    *,
    db_session,
) -> SessionTutorGraphState:
    _trace(state, "persist_assistant_message")
    response = await create_message_with_response(
        session=db_session,
        tenant_id=uuid.UUID(state["tenant_id"]),
        session_id=uuid.UUID(state["session_id"]),
        payload=MessageCreate(
            role=MessageRole.assistant,
            content=state["answer"],
            citations=[
                MessageCitationCreate(
                    source_id=uuid.UUID(citation["source_id"]),
                    source_chunk_id=uuid.UUID(citation["chunk_id"]),
                    quote=citation["text"],
                    citation={
                        "source_filename": citation["source_filename"],
                        "chunk_index": citation["chunk_index"],
                    },
                )
                for citation in state.get("citations", [])
            ],
        ),
    )
    state["assistant_message_id"] = str(response.id)
    state["assistant_response"] = _message_response_payload(response)
    return state


def extract_learning_signals(state: SessionTutorGraphState) -> SessionTutorGraphState:
    _trace(state, "extract_learning_signals")
    state["learning_signals"] = build_learning_signals(
        content=state["content"],
        citation_count=len(state.get("citations", [])),
        chapter_supervision=state.get("chapter_supervision"),
    )
    return state


async def record_graph_agent_run(
    state: SessionTutorGraphState,
    *,
    db_session,
) -> SessionTutorGraphState:
    _trace(state, "record_agent_run")
    assistant_message_id = state.get("assistant_message_id")
    await record_agent_run(
        session=db_session,
        tenant_id=uuid.UUID(state["tenant_id"]),
        session_id=uuid.UUID(state["session_id"]),
        message_id=uuid.UUID(assistant_message_id) if assistant_message_id else None,
        input_payload={
            "content": state["content"],
            "user_message_id": str(state.get("user_message_id")),
            "chapter_supervision_used": state.get("chapter_supervision") is not None,
        },
        output_payload={
            "assistant_message_id": str(state.get("assistant_message_id")),
            "citation_count": len(state.get("citations", [])),
            "node_trace": state["node_trace"],
            "learning_signals": state["learning_signals"],
            "chapter_supervision_used": state.get("chapter_supervision") is not None,
        },
        model="langgraph:deterministic",
        status=AgentRunStatus.completed,
    )
    return state
