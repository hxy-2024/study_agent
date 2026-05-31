import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.core.config import get_settings
from app.db.session import get_db_session
from app.domain.local_settings.service import load_local_ai_settings
from app.domain.rag.embeddings import create_embedding_provider_from_preset
from app.domain.rag.ingestion import ingest_source
from app.domain.rag.schemas import IngestSourceRequest, IngestSourceResponse
from app.infrastructure.storage import create_runtime_text_source_reader

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/sources/{source_id}/run", response_model=IngestSourceResponse)
async def run_source_ingestion(
    source_id: uuid.UUID,
    payload: IngestSourceRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    context: CurrentUserContext = Depends(get_authorized_user_context),
) -> IngestSourceResponse:
    settings = get_settings()
    try:
        embedding_provider = create_embedding_provider_from_preset(
            payload.embedding_preset if payload else None,
            dimension=settings.rag_embedding_dimension,
            local_ai_settings=load_local_ai_settings(path=settings.local_settings_path),
            runtime_settings=settings,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        result = await ingest_source(
            session=session,
            source_id=source_id,
            reader=create_runtime_text_source_reader(),
            embedding_provider=embedding_provider,
            max_chars=settings.rag_chunk_max_chars,
            overlap_chars=settings.rag_chunk_overlap_chars,
            tenant_id=context.tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    status = result.status.value if hasattr(result.status, "value") else result.status
    return IngestSourceResponse(
        job_id=result.job_id,
        source_id=result.source_id,
        status=status,
        chunk_count=result.chunk_count,
    )
