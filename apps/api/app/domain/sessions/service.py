import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRun,
    AgentRunStatus,
    AgentType,
    Chapter,
    Message,
    MessageCitation,
    MessageRole,
    Session,
    SessionStatus,
)
from app.core.config import get_settings
from app.domain.agent_runtime.config import graph_runtime_config_from_settings
from app.domain.chapter_mentor.providers import AnswerProvider
from app.domain.chapter_mentor.service import load_source_filenames
from app.domain.rag.embeddings import EmbeddingProvider
from app.domain.rag.retrieval import retrieve_chunks
from app.domain.sessions.schemas import (
    MessageCreate,
    MessageCitationCreate,
    MessageCitationResponse,
    MessageResponse,
    SessionCreate,
    SessionResponse,
)


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def build_session_response(session: Session) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        study_space_id=session.study_space_id,
        chapter_id=session.chapter_id,
        title=session.title,
        status=_enum_value(session.status),
        summary=session.summary,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def build_message_response(message, citations: list[MessageCitation]) -> MessageResponse:
    def citation_filename(citation: MessageCitation) -> str:
        metadata = citation.citation or {}
        return str(metadata.get("source_filename") or "Unknown source")

    def citation_chunk_index(citation: MessageCitation) -> int:
        metadata = citation.citation or {}
        raw_index = metadata.get("chunk_index", 0)
        return raw_index if isinstance(raw_index, int) else 0

    def citation_source_jump(citation: MessageCitation) -> dict[str, str]:
        metadata = citation.citation or {}
        space_id = getattr(message, "study_space_id", None) or metadata.get("space_id") or metadata.get("study_space_id")
        return {
            "space_id": str(space_id),
            "source_id": str(citation.source_id),
            "chunk_id": str(citation.source_chunk_id),
            "source_url": f"/spaces/{space_id}?source_id={citation.source_id}",
            "chunk_url": f"/spaces/{space_id}?source_id={citation.source_id}&chunk_id={citation.source_chunk_id}",
        }

    return MessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=_enum_value(message.role),
        content=message.content,
        metadata=getattr(message, "metadata_", {}) or {},
        citations=[
            MessageCitationResponse(
                id=citation.id,
                message_id=citation.message_id,
                source_id=citation.source_id,
                source_chunk_id=citation.source_chunk_id,
                chunk_id=citation.source_chunk_id,
                source_jump=citation_source_jump(citation),
                source_filename=citation_filename(citation),
                chunk_index=citation_chunk_index(citation),
                text=citation.quote,
                quote=citation.quote,
                citation=citation.citation or {},
            )
            for citation in citations
        ],
        created_at=message.created_at,
    )


async def ensure_chapter_in_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> Chapter:
    chapter = await session.scalar(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.tenant_id == tenant_id,
        )
    )
    if chapter is None:
        raise ValueError("Chapter not found for tenant")
    return chapter


async def ensure_session_in_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
) -> Session:
    tutor_session = await session.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.tenant_id == tenant_id,
        )
    )
    if tutor_session is None:
        raise ValueError("Session not found for tenant")
    return tutor_session


async def create_session_for_chapter(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
    payload: SessionCreate,
) -> Session:
    chapter = await ensure_chapter_in_tenant(
        session=session,
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )
    tutor_session = Session(
        tenant_id=tenant_id,
        study_space_id=chapter.study_space_id,
        chapter_id=chapter.id,
        title=payload.title or f"{chapter.title} tutoring session",
        status=SessionStatus.active,
    )
    session.add(tutor_session)
    await session.commit()
    await session.refresh(tutor_session)
    return tutor_session


async def list_sessions_for_chapter(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> list[Session]:
    await ensure_chapter_in_tenant(
        session=session,
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )
    rows = await session.scalars(
        select(Session)
        .where(
            Session.tenant_id == tenant_id,
            Session.chapter_id == chapter_id,
        )
        .order_by(Session.created_at.desc(), Session.id)
    )
    return list(rows)


async def delete_session(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await ensure_session_in_tenant(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
    )
    message_ids = select(Message.id).where(
        Message.tenant_id == tenant_id,
        Message.session_id == session_id,
    )
    await session.execute(
        delete(AgentRun).where(
            AgentRun.tenant_id == tenant_id,
            AgentRun.session_id == session_id,
        )
    )
    await session.execute(
        delete(MessageCitation).where(MessageCitation.message_id.in_(message_ids))
    )
    await session.execute(
        delete(Message).where(
            Message.tenant_id == tenant_id,
            Message.session_id == session_id,
        )
    )
    await session.execute(
        delete(Session).where(
            Session.tenant_id == tenant_id,
            Session.id == session_id,
        )
    )
    await session.commit()


async def rename_session(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    title: str,
) -> Session:
    tutor_session = await ensure_session_in_tenant(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
    )
    tutor_session.title = title.strip()
    await session.commit()
    await session.refresh(tutor_session)
    return tutor_session


async def create_message(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: MessageCreate,
) -> Message:
    tutor_session = await ensure_session_in_tenant(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
    )
    message = Message(
        tenant_id=tenant_id,
        study_space_id=tutor_session.study_space_id,
        session_id=tutor_session.id,
        role=payload.role,
        content=payload.content,
        metadata_=payload.metadata,
    )
    session.add(message)
    await session.flush()

    for citation in payload.citations:
        session.add(
            MessageCitation(
                tenant_id=tenant_id,
                message_id=message.id,
                source_id=citation.source_id,
                source_chunk_id=citation.source_chunk_id,
                quote=citation.quote,
                citation=citation.citation,
            )
        )

    await session.commit()
    await session.refresh(message)
    return message


async def create_message_with_response(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: MessageCreate,
) -> MessageResponse:
    message = await create_message(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
        payload=payload,
    )
    return build_message_response(
        message=message,
        citations=[
            MessageCitation(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                message_id=message.id,
                source_id=citation.source_id,
                source_chunk_id=citation.source_chunk_id,
                quote=citation.quote,
                citation=citation.citation,
            )
            for citation in payload.citations
        ],
    )


async def list_messages_for_session(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
) -> list[MessageResponse]:
    await ensure_session_in_tenant(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
    )
    message_rows = await session.scalars(
        select(Message)
        .where(
            Message.tenant_id == tenant_id,
            Message.session_id == session_id,
        )
        .order_by(Message.created_at, Message.id)
    )
    messages = list(message_rows)
    if not messages:
        return []

    citation_rows = await session.scalars(
        select(MessageCitation)
        .where(MessageCitation.message_id.in_([message.id for message in messages]))
        .order_by(MessageCitation.created_at, MessageCitation.id)
    )
    citations_by_message: dict[uuid.UUID, list[MessageCitation]] = {
        message.id: [] for message in messages
    }
    for citation in citation_rows:
        citations_by_message.setdefault(citation.message_id, []).append(citation)

    return [
        build_message_response(
            message=message,
            citations=citations_by_message.get(message.id, []),
        )
        for message in messages
    ]


async def record_agent_run(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    input_payload: dict,
    output_payload: dict,
    model: str | None = None,
    message_id: uuid.UUID | None = None,
    status: AgentRunStatus = AgentRunStatus.completed,
    error_message: str | None = None,
    latency_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
) -> AgentRun:
    tutor_session = await ensure_session_in_tenant(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
    )
    run = AgentRun(
        tenant_id=tenant_id,
        study_space_id=tutor_session.study_space_id,
        session_id=tutor_session.id,
        message_id=message_id,
        agent_type=AgentType.session_tutor,
        status=status,
        model=model,
        input_payload=input_payload,
        output_payload=output_payload,
        error_message=error_message,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        completed_at=(
            datetime.now(UTC)
            if status in {AgentRunStatus.completed, AgentRunStatus.failed}
            else None
        ),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def answer_session_message(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    embedding_provider: EmbeddingProvider,
    answer_provider: AnswerProvider,
    web_search_enabled: bool | None = None,
) -> MessageResponse:
    runtime_config = graph_runtime_config_from_settings(get_settings())
    if not runtime_config.session_tutor_graph_enabled:
        return await _answer_session_message_without_graph(
            session=session,
            tenant_id=tenant_id,
            session_id=session_id,
            content=content,
            embedding_provider=embedding_provider,
            answer_provider=answer_provider,
            web_search_enabled=web_search_enabled,
        )

    from app.domain.session_tutor_graph.service import run_session_tutor_graph

    return await run_session_tutor_graph(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        content=content,
        embedding_provider=embedding_provider,
        answer_provider=answer_provider,
        web_search_enabled=web_search_enabled,
    )


async def _answer_session_message_without_graph(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    embedding_provider: EmbeddingProvider,
    answer_provider: AnswerProvider,
    web_search_enabled: bool | None = None,
) -> MessageResponse:
    tutor_session = await ensure_session_in_tenant(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
    )
    chapter = await ensure_chapter_in_tenant(
        session=session,
        tenant_id=tenant_id,
        chapter_id=tutor_session.chapter_id,
    )
    user_message = await create_message(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
        payload=MessageCreate(role=MessageRole.user, content=content),
    )
    query = f"{chapter.title}\n{getattr(chapter, 'goal', '')}\n{content}"
    chunks = await retrieve_chunks(
        session=session,
        tenant_id=tenant_id,
        study_space_id=tutor_session.study_space_id,
        query=query,
        limit=5,
        embedding_provider=embedding_provider,
    )
    source_filenames = await load_source_filenames(
        session=session,
        tenant_id=tenant_id,
        study_space_id=tutor_session.study_space_id,
        source_ids=[chunk.source_id for chunk in chunks],
    )
    mentor_response = await answer_provider.answer(
        question=content,
        chunks=chunks,
        source_filenames=source_filenames,
        web_search_results=[],
    )
    assistant_response = await create_message_with_response(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
        payload=MessageCreate(
            role=MessageRole.assistant,
            content=mentor_response.answer,
            metadata={
                "runtime": "deterministic",
                "graph_enabled": False,
                "web_search_enabled": bool(web_search_enabled),
            },
            citations=[
                MessageCitationCreate(
                    source_id=citation.source_id,
                    source_chunk_id=citation.chunk_id,
                    quote=citation.text,
                    citation={
                        "source_filename": citation.source_filename,
                        "chunk_index": citation.chunk_index,
                        "graph_enabled": False,
                    },
                )
                for citation in mentor_response.citations
            ],
        ),
    )
    await record_agent_run(
        session=session,
        tenant_id=tenant_id,
        session_id=session_id,
        message_id=assistant_response.id,
        input_payload={
            "content": content,
            "user_message_id": str(user_message.id),
            "graph_enabled": False,
            "web_search_enabled": bool(web_search_enabled),
        },
        output_payload={
            "assistant_message_id": str(assistant_response.id),
            "citation_count": len(assistant_response.citations),
            "graph_enabled": False,
            "web_search_enabled": bool(web_search_enabled),
        },
        model="deterministic",
        status=AgentRunStatus.completed,
    )
    return assistant_response
