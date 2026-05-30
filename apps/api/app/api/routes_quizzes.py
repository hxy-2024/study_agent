import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.quizzes.schemas import (
    GenerateQuizRequest,
    MasteryRecordResponse,
    QuizResponse,
    QuizSubmissionResponse,
    SubmitQuizRequest,
)
from app.domain.quizzes.service import (
    generate_chapter_quiz,
    get_chapter_mastery,
    get_latest_quiz_result,
    get_quiz,
    mastery_record_response,
    retake_quiz,
    submit_quiz_answers,
)

router = APIRouter(tags=["quizzes"])


def map_quiz_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 404 if "not found" in message.lower() else 400
    return HTTPException(status_code=status_code, detail=message)


@router.post(
    "/chapters/{chapter_id}/quizzes/generate",
    response_model=QuizResponse,
    status_code=201,
)
async def generate_quiz_for_chapter(
    chapter_id: uuid.UUID,
    payload: GenerateQuizRequest | None = None,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> QuizResponse:
    request = payload or GenerateQuizRequest()
    try:
        return await generate_chapter_quiz(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            chapter_id=chapter_id,
            question_count=request.question_count,
        )
    except ValueError as exc:
        raise map_quiz_error(exc) from exc


@router.get("/quizzes/{quiz_id}", response_model=QuizResponse)
async def read_quiz(
    quiz_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> QuizResponse:
    try:
        return await get_quiz(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            quiz_id=quiz_id,
        )
    except ValueError as exc:
        raise map_quiz_error(exc) from exc


@router.post("/quizzes/{quiz_id}/retake", response_model=QuizResponse, status_code=201)
async def retake_existing_quiz(
    quiz_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> QuizResponse:
    try:
        return await retake_quiz(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            quiz_id=quiz_id,
        )
    except ValueError as exc:
        raise map_quiz_error(exc) from exc


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizSubmissionResponse)
async def submit_quiz(
    quiz_id: uuid.UUID,
    payload: SubmitQuizRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> QuizSubmissionResponse:
    try:
        return await submit_quiz_answers(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            quiz_id=quiz_id,
            answers=payload.answers,
        )
    except ValueError as exc:
        raise map_quiz_error(exc) from exc


@router.get("/quizzes/{quiz_id}/result", response_model=QuizSubmissionResponse)
async def read_latest_quiz_result(
    quiz_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> QuizSubmissionResponse:
    try:
        result = await get_latest_quiz_result(
            session=session,
            tenant_id=context.tenant_id,
            quiz_id=quiz_id,
            user_id=context.user_id,
        )
    except ValueError as exc:
        raise map_quiz_error(exc) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Quiz result not found for tenant")
    return result


@router.get("/chapters/{chapter_id}/mastery", response_model=MasteryRecordResponse)
async def read_chapter_mastery(
    chapter_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> MasteryRecordResponse:
    try:
        mastery = await get_chapter_mastery(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            chapter_id=chapter_id,
        )
    except ValueError as exc:
        raise map_quiz_error(exc) from exc
    if mastery is None:
        raise HTTPException(status_code=404, detail="Mastery record not found for tenant")
    if isinstance(mastery, MasteryRecordResponse):
        return mastery
    return mastery_record_response(mastery)
