import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.ingestion import ingest_source
from app.domain.rag.schemas import IngestSourceResponse
from app.infrastructure.storage import TextSourceReader

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class UnsupportedRuntimeTextReader(TextSourceReader):
    async def read_text(self, object_key: str) -> str:
        raise RuntimeError(f"Runtime text reader is not configured for {object_key}")


@router.post("/sources/{source_id}/run", response_model=IngestSourceResponse)
async def run_source_ingestion(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> IngestSourceResponse:
    settings = get_settings()
    embedding_provider = DeterministicEmbeddingProvider(settings.rag_embedding_dimension)
    try:
        result = await ingest_source(
            session=session,
            source_id=source_id,
            reader=UnsupportedRuntimeTextReader(),
            embedding_provider=embedding_provider,
            max_chars=settings.rag_chunk_max_chars,
            overlap_chars=settings.rag_chunk_overlap_chars,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    return IngestSourceResponse(
        job_id=result.job_id,
        source_id=result.source_id,
        status=result.status.value,
        chunk_count=result.chunk_count,
    )
