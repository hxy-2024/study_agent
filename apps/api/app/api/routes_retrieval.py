from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.core.config import get_settings
from app.db.session import get_db_session
from app.domain.local_settings.service import load_local_ai_settings
from app.domain.rag.embeddings import create_embedding_provider_from_preset
from app.domain.rag.retrieval import retrieve_chunks
from app.domain.rag.schemas import RetrieveRequest, RetrieveResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_rag_chunks(
    payload: RetrieveRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> RetrieveResponse:
    settings = get_settings()
    try:
        embedding_provider = create_embedding_provider_from_preset(
            None,
            dimension=settings.rag_embedding_dimension,
            local_ai_settings=load_local_ai_settings(path=settings.local_settings_path),
            runtime_settings=settings,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        chunks = await retrieve_chunks(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=payload.study_space_id,
            query=payload.query,
            limit=payload.limit,
            embedding_provider=embedding_provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RetrieveResponse(
        query=payload.query,
        chunks=[
            {
                "chunk_id": chunk.id,
                "source_id": chunk.source_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "citation": chunk.citation,
                "score": chunk.score,
            }
            for chunk in chunks
        ],
    )
