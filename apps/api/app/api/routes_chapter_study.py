import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.core.config import get_settings
from app.db.session import get_db_session
from app.domain.chapter_mentor.schemas import ChapterMentorQuestionRequest, ChapterMentorResponse
from app.domain.chapter_mentor.service import ask_chapter_mentor
from app.domain.chapter_study.schemas import ChapterStudyDetailResponse
from app.domain.chapter_study.service import complete_chapter, get_chapter_detail
from app.domain.rag.embeddings import DeterministicEmbeddingProvider

router = APIRouter(tags=["chapter-study"])


def map_chapter_error(exc: ValueError) -> HTTPException:
    status_code = 404 if "not found" in str(exc).lower() else 400
    return HTTPException(status_code=status_code, detail=str(exc))


@router.get("/chapters/{chapter_id}", response_model=ChapterStudyDetailResponse)
async def read_chapter_detail(
    chapter_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterStudyDetailResponse:
    try:
        return await get_chapter_detail(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=chapter_id,
        )
    except ValueError as exc:
        raise map_chapter_error(exc) from exc


@router.post("/chapters/{chapter_id}/complete", response_model=ChapterStudyDetailResponse)
async def mark_chapter_complete(
    chapter_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterStudyDetailResponse:
    try:
        return await complete_chapter(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=chapter_id,
        )
    except ValueError as exc:
        raise map_chapter_error(exc) from exc


@router.post("/chapters/{chapter_id}/mentor/questions", response_model=ChapterMentorResponse)
async def ask_chapter_mentor_question(
    chapter_id: uuid.UUID,
    payload: ChapterMentorQuestionRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterMentorResponse:
    settings = get_settings()
    try:
        embedding_provider = DeterministicEmbeddingProvider(
            dimension=settings.rag_embedding_dimension
        )
        return await ask_chapter_mentor(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=chapter_id,
            question=payload.question,
            embedding_provider=embedding_provider,
        )
    except ValueError as exc:
        raise map_chapter_error(exc) from exc
