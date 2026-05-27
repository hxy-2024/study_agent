import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.sources.schemas import SourceChunkListResponse, SourceListResponse, SourceUploadedResponse
from app.domain.sources.service import list_source_chunks, list_sources_for_space, mark_source_uploaded

router = APIRouter(tags=["sources"])


@router.get("/study-spaces/{study_space_id}/sources", response_model=SourceListResponse)
async def list_sources(
    study_space_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: CurrentUserContext = Depends(get_authorized_user_context),
) -> SourceListResponse:
    try:
        sources = await list_sources_for_space(session, study_space_id, context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SourceListResponse(sources=sources)


@router.post("/sources/{source_id}/uploaded", response_model=SourceUploadedResponse)
async def upload_source(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: CurrentUserContext = Depends(get_authorized_user_context),
) -> SourceUploadedResponse:
    try:
        source = await mark_source_uploaded(session, source_id, context.tenant_id)
    except ValueError as exc:
        status_code = 404 if str(exc) == "Source not found for tenant" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SourceUploadedResponse(source=source)


@router.get("/sources/{source_id}/chunks", response_model=SourceChunkListResponse)
async def get_source_chunks(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: CurrentUserContext = Depends(get_authorized_user_context),
) -> SourceChunkListResponse:
    try:
        chunks = await list_source_chunks(session, source_id, context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SourceChunkListResponse(chunks=chunks)
