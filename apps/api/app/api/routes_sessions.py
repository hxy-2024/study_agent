import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.core.config import get_settings
from app.db.session import get_db_session
from app.domain.chapter_mentor.providers import create_answer_provider
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.sessions.schemas import (
    MessageResponse,
    SessionCreate,
    SessionResponse,
    SessionUpdate,
    TutorMessageRequest,
)
from app.domain.sessions.service import (
    answer_session_message,
    build_session_response,
    create_session_for_chapter,
    delete_session,
    list_messages_for_session,
    list_sessions_for_chapter,
    rename_session,
)

router = APIRouter(tags=["sessions"])


def map_session_error(exc: ValueError) -> HTTPException:
    status_code = 404 if "not found" in str(exc).lower() else 400
    return HTTPException(status_code=status_code, detail=str(exc))


@router.get("/chapters/{chapter_id}/sessions", response_model=list[SessionResponse])
async def read_chapter_sessions(
    chapter_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[SessionResponse]:
    try:
        rows = await list_sessions_for_chapter(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=chapter_id,
        )
    except ValueError as exc:
        raise map_session_error(exc) from exc
    return [build_session_response(row) for row in rows]


@router.post(
    "/chapters/{chapter_id}/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter_session(
    chapter_id: uuid.UUID,
    payload: SessionCreate | None = None,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    try:
        row = await create_session_for_chapter(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=chapter_id,
            payload=payload or SessionCreate(),
        )
    except ValueError as exc:
        raise map_session_error(exc) from exc
    return build_session_response(row)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def read_session_messages(
    session_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[MessageResponse]:
    try:
        return await list_messages_for_session(
            session=session,
            tenant_id=context.tenant_id,
            session_id=session_id,
        )
    except ValueError as exc:
        raise map_session_error(exc) from exc


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tutor_session(
    session_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await delete_session(
            session=session,
            tenant_id=context.tenant_id,
            session_id=session_id,
        )
    except ValueError as exc:
        raise map_session_error(exc) from exc


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def rename_tutor_session(
    session_id: uuid.UUID,
    payload: SessionUpdate,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    try:
        row = await rename_session(
            session=session,
            tenant_id=context.tenant_id,
            session_id=session_id,
            title=payload.title,
        )
    except ValueError as exc:
        raise map_session_error(exc) from exc
    return build_session_response(row)


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def create_tutor_message(
    session_id: uuid.UUID,
    payload: TutorMessageRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    settings = get_settings()
    try:
        return await answer_session_message(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            session_id=session_id,
            content=payload.content,
            embedding_provider=DeterministicEmbeddingProvider(settings.rag_embedding_dimension),
            answer_provider=create_answer_provider(
                settings,
                agent_layer="session_tutor",
                model_override=payload.model,
            ),
            web_search_enabled=payload.web_search_enabled,
            thinking_effort=payload.thinking_effort,
        )
    except ValueError as exc:
        raise map_session_error(exc) from exc
