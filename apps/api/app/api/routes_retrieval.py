from fastapi import APIRouter, HTTPException

from app.domain.rag.schemas import RetrieveRequest, RetrieveResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_rag_chunks(
    payload: RetrieveRequest,
) -> RetrieveResponse:
    raise HTTPException(
        status_code=501,
        detail=(
            "Runtime retrieval API requires authenticated tenant context "
            "before it can return source chunks"
        ),
    )
