import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Chapter,
    ChapterMentorState,
    MasteryLevel,
    MasteryRecord,
    Quiz,
    QuizQuestion,
    QuizStatus,
    QuizSubmission,
    Source,
    SourceChunk,
)
from app.domain.quizzes.schemas import (
    MasteryRecordResponse,
    QuizEvidenceResponse,
    QuizQuestionResponse,
    QuizQuestionResultResponse,
    QuizResponse,
    QuizSubmissionResponse,
)


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _preview(text: str, limit: int = 120) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def build_evidence_response(evidence: dict | None) -> QuizEvidenceResponse:
    evidence = evidence or {}
    return QuizEvidenceResponse(
        source_filename=evidence.get("source_filename"),
        chunk_index=evidence.get("chunk_index"),
        text=evidence.get("text"),
    )


def calculate_mastery_level(score_percent: int) -> MasteryLevel:
    if score_percent >= 90:
        return MasteryLevel.mastered
    if score_percent >= 70:
        return MasteryLevel.proficient
    if score_percent >= 40:
        return MasteryLevel.developing
    return MasteryLevel.new


async def ensure_chapter_for_quiz(
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


def _referenced_chunk_ids(source_chunk_refs: list[dict]) -> list[uuid.UUID]:
    chunk_ids: list[uuid.UUID] = []
    for ref in source_chunk_refs:
        raw_id = ref.get("chunk_id")
        if raw_id is None:
            continue
        try:
            chunk_ids.append(uuid.UUID(str(raw_id)))
        except ValueError:
            continue
    return chunk_ids


async def load_chapter_quiz_evidence(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter: Chapter,
) -> list[tuple[SourceChunk, Source]]:
    chunk_ids = _referenced_chunk_ids(chapter.source_chunk_refs or [])
    if not chunk_ids:
        return []

    rows = await session.execute(
        select(SourceChunk, Source)
        .join(Source, Source.id == SourceChunk.source_id)
        .where(
            SourceChunk.id.in_(chunk_ids),
            SourceChunk.tenant_id == tenant_id,
            SourceChunk.study_space_id == chapter.study_space_id,
            SourceChunk.is_active.is_(True),
            Source.tenant_id == tenant_id,
            Source.study_space_id == chapter.study_space_id,
        )
        .order_by(SourceChunk.chunk_index, SourceChunk.id)
    )
    return list(rows.all())


async def load_chapter_mentor_summary(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> ChapterMentorState | None:
    return await session.scalar(
        select(ChapterMentorState).where(
            ChapterMentorState.tenant_id == tenant_id,
            ChapterMentorState.chapter_id == chapter_id,
        )
    )


def deterministic_questions(
    chapter: Chapter,
    evidence_rows: list[tuple[SourceChunk, Source]],
    mentor_state: ChapterMentorState | None = None,
    question_count: int = 3,
) -> list[dict]:
    count = max(1, min(question_count, 5))
    evidence_rows = evidence_rows[:count]
    questions: list[dict] = []
    weak_point = ""
    if mentor_state is not None and mentor_state.weak_points:
        weak_point = mentor_state.weak_points[0]

    for index in range(count):
        evidence_pair = evidence_rows[index] if index < len(evidence_rows) else None
        chunk = evidence_pair[0] if evidence_pair else None
        source = evidence_pair[1] if evidence_pair else None
        evidence_text = _preview(chunk.text if chunk is not None else chapter.summary)
        evidence = {
            "chunk_id": str(chunk.id) if chunk is not None else None,
            "source_id": str(source.id) if source is not None else None,
            "source_filename": source.filename if source is not None else None,
            "chunk_index": chunk.chunk_index if chunk is not None else None,
            "citation": chunk.citation if chunk is not None else {},
            "text": evidence_text,
        }
        option_sets = [
            [
                "Start from the chapter goal, then verify claims against the linked evidence.",
                "Read the source once, then rely on memory for the rest of the chapter.",
                "Focus on terminology before checking whether the evidence supports it.",
                "Compare every source chunk equally, even when it does not match the question.",
            ],
            [
                "Use the citation text as the anchor for the answer.",
                "Use the file name as the only evidence signal.",
                "Use the longest option as the strongest answer.",
                "Use the newest quiz result as the source citation.",
            ],
            [
                "Turn the weak point into a targeted review question.",
                "Mark the chapter complete as soon as a weak point appears.",
                "Delete the weak point after one incorrect answer.",
                "Replace source review with a new route generation run.",
            ],
            [
                "Preserve the source context that directly supports the explanation.",
                "Preserve only the chapter title because it is easier to scan.",
                "Preserve unrelated metadata before reading the cited text.",
                "Preserve the object key instead of the learning evidence.",
            ],
            [
                "Update the learner's chapter mastery from the submitted quiz result.",
                "Update the tenant settings from the submitted quiz result.",
                "Update the storage object key from the submitted quiz result.",
                "Update every learner's mastery from one submitted quiz result.",
            ],
        ]
        base_options = option_sets[index % len(option_sets)]
        rotation = index % len(base_options)
        options = base_options[rotation:] + base_options[:rotation]
        correct_option_index = (len(base_options) - rotation) % len(base_options)
        prompt = f"{chapter.title}: which choice best supports the chapter goal?"
        if weak_point:
            prompt = f"{prompt} Focus on: {weak_point}."
        questions.append(
            {
                "order_index": index + 1,
                "prompt": prompt,
                "options": options,
                "correct_option_index": correct_option_index,
                "explanation": f"The cited evidence supports {chapter.goal}: {evidence_text}",
                "evidence": evidence,
            }
        )
    return questions


def build_quiz_response(quiz: Quiz, questions: list[QuizQuestion]) -> QuizResponse:
    return QuizResponse(
        id=quiz.id,
        study_space_id=quiz.study_space_id,
        chapter_id=quiz.chapter_id,
        title=quiz.title,
        status=_enum_value(quiz.status),
        generation_strategy=quiz.generation_strategy or "deterministic",
        question_count=quiz.question_count,
        questions=[
            QuizQuestionResponse(
                id=question.id,
                order_index=question.order_index,
                prompt=question.prompt,
                options=question.options,
                evidence=build_evidence_response(question.evidence),
            )
            for question in questions
        ],
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
    )


async def generate_chapter_quiz(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    chapter_id: uuid.UUID,
    question_count: int = 3,
) -> QuizResponse:
    chapter = await ensure_chapter_for_quiz(session=session, tenant_id=tenant_id, chapter_id=chapter_id)
    evidence_rows = await load_chapter_quiz_evidence(session=session, tenant_id=tenant_id, chapter=chapter)
    mentor_state = await load_chapter_mentor_summary(session=session, tenant_id=tenant_id, chapter_id=chapter.id)
    drafts = deterministic_questions(
        chapter=chapter,
        evidence_rows=evidence_rows,
        mentor_state=mentor_state,
        question_count=question_count,
    )
    quiz = Quiz(
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=chapter.study_space_id,
        chapter_id=chapter.id,
        title=f"{chapter.title} Quiz",
        status=QuizStatus.active,
        generation_strategy="deterministic",
        question_count=len(drafts),
    )
    session.add(quiz)
    await session.flush()

    questions = [
        QuizQuestion(
            tenant_id=tenant_id,
            quiz_id=quiz.id,
            chapter_id=chapter.id,
            order_index=draft["order_index"],
            prompt=draft["prompt"],
            options=draft["options"],
            correct_option_index=draft["correct_option_index"],
            explanation=draft["explanation"],
            evidence=draft["evidence"],
        )
        for draft in drafts
    ]
    for question in questions:
        session.add(question)
    await session.flush()
    await session.commit()
    await session.refresh(quiz)
    return build_quiz_response(quiz=quiz, questions=questions)


async def load_quiz_with_questions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    quiz_id: uuid.UUID,
    for_update: bool = False,
) -> tuple[Quiz, list[QuizQuestion]]:
    quiz_statement = select(Quiz).where(
        Quiz.id == quiz_id,
        Quiz.tenant_id == tenant_id,
        Quiz.user_id == user_id,
    )
    if for_update:
        quiz_statement = quiz_statement.with_for_update()
    quiz = await session.scalar(quiz_statement)
    if quiz is None:
        raise ValueError("Quiz not found for tenant")

    question_rows = await session.scalars(
        select(QuizQuestion)
        .where(
            QuizQuestion.tenant_id == tenant_id,
            QuizQuestion.quiz_id == quiz.id,
            QuizQuestion.chapter_id == quiz.chapter_id,
        )
        .order_by(QuizQuestion.order_index)
    )
    return quiz, list(question_rows)


async def get_quiz(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    quiz_id: uuid.UUID,
) -> QuizResponse:
    quiz, questions = await load_quiz_with_questions(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        quiz_id=quiz_id,
        for_update=True,
    )
    return build_quiz_response(quiz=quiz, questions=questions)


def validate_answers(questions: list[QuizQuestion], answers: list[int]) -> None:
    if len(answers) != len(questions):
        raise ValueError("Quiz answer count does not match question count")
    for index, (question, answer) in enumerate(zip(questions, answers, strict=True), start=1):
        if answer < 0 or answer >= len(question.options):
            raise ValueError(f"Quiz answer for question {index} is out of range")


def build_results(
    questions: list[QuizQuestion],
    answers: list[int],
) -> tuple[list[QuizQuestionResultResponse], int, list[str]]:
    results: list[QuizQuestionResultResponse] = []
    weak_points: list[str] = []
    correct_count = 0
    for question, answer in zip(questions, answers, strict=True):
        is_correct = answer == question.correct_option_index
        if is_correct:
            correct_count += 1
        else:
            weak_points.append(question.prompt)
        results.append(
            QuizQuestionResultResponse(
                question_id=question.id,
                order_index=question.order_index,
                prompt=question.prompt,
                selected_option_index=answer,
                correct_option_index=question.correct_option_index,
                is_correct=is_correct,
                explanation=question.explanation,
                evidence=build_evidence_response(question.evidence),
            )
        )
    return results, correct_count, weak_points


async def get_chapter_mastery(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> MasteryRecord | None:
    return await session.scalar(
        select(MasteryRecord).where(
            MasteryRecord.tenant_id == tenant_id,
            MasteryRecord.user_id == user_id,
            MasteryRecord.chapter_id == chapter_id,
        )
    )


async def lock_chapter_mastery_scope(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> None:
    locked_chapter_id = await session.scalar(
        select(Chapter.id)
        .where(
            Chapter.id == chapter_id,
            Chapter.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    if locked_chapter_id is None:
        raise ValueError("Chapter not found for tenant")


def mastery_record_response(mastery: MasteryRecord) -> MasteryRecordResponse:
    return MasteryRecordResponse(
        id=mastery.id,
        study_space_id=mastery.study_space_id,
        chapter_id=mastery.chapter_id,
        score_percent=mastery.score_percent,
        level=_enum_value(mastery.level),
        weak_points=mastery.weak_points or [],
        last_quiz_submission_id=mastery.last_quiz_submission_id,
        updated_at=mastery.updated_at,
    )


async def upsert_mastery_record(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    quiz: Quiz,
    submission: QuizSubmission,
    weak_points: list[str],
) -> MasteryRecord:
    await lock_chapter_mastery_scope(session=session, tenant_id=tenant_id, chapter_id=quiz.chapter_id)
    mastery = await get_chapter_mastery(
        session=session,
        tenant_id=tenant_id,
        user_id=submission.user_id,
        chapter_id=quiz.chapter_id,
    )
    if mastery is None:
        mastery = MasteryRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=submission.user_id,
            study_space_id=quiz.study_space_id,
            chapter_id=quiz.chapter_id,
            score_percent=submission.score_percent,
            level=calculate_mastery_level(submission.score_percent),
            weak_points=weak_points,
            last_quiz_submission_id=submission.id,
            updated_at=datetime.now(UTC),
        )
        session.add(mastery)
    else:
        mastery.score_percent = submission.score_percent
        mastery.level = calculate_mastery_level(submission.score_percent)
        mastery.weak_points = weak_points
        mastery.last_quiz_submission_id = submission.id
        mastery.updated_at = datetime.now(UTC)
    return mastery


def build_submission_response(
    submission: QuizSubmission,
    results: list[QuizQuestionResultResponse],
    mastery: MasteryRecord,
) -> QuizSubmissionResponse:
    return QuizSubmissionResponse(
        id=submission.id,
        quiz_id=submission.quiz_id,
        chapter_id=submission.chapter_id,
        user_id=submission.user_id,
        answers=submission.answers,
        score_percent=submission.score_percent,
        correct_count=submission.correct_count,
        question_count=submission.question_count,
        results=results,
        weak_points=submission.weak_points or [],
        mastery=mastery_record_response(mastery),
        created_at=submission.created_at,
    )


async def submit_quiz_answers(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    quiz_id: uuid.UUID,
    answers: list[int],
) -> QuizSubmissionResponse:
    quiz, questions = await load_quiz_with_questions(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        quiz_id=quiz_id,
        for_update=True,
    )
    if quiz.status == QuizStatus.submitted:
        raise ValueError("Quiz already submitted")
    validate_answers(questions=questions, answers=answers)
    results, correct_count, weak_points = build_results(questions=questions, answers=answers)
    question_count = len(questions)
    score_percent = int(round((correct_count / question_count) * 100)) if question_count else 0
    submission = QuizSubmission(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        quiz_id=quiz.id,
        chapter_id=quiz.chapter_id,
        user_id=user_id,
        answers=answers,
        score_percent=score_percent,
        correct_count=correct_count,
        question_count=question_count,
        results=[result.model_dump(mode="json") for result in results],
        weak_points=weak_points,
    )
    session.add(submission)
    quiz.status = QuizStatus.submitted
    mastery = await upsert_mastery_record(
        session=session,
        tenant_id=tenant_id,
        quiz=quiz,
        submission=submission,
        weak_points=weak_points,
    )
    await session.flush()
    await session.commit()
    await session.refresh(submission)
    await session.refresh(mastery)
    return build_submission_response(submission=submission, results=results, mastery=mastery)


async def get_latest_quiz_result(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    quiz_id: uuid.UUID,
    user_id: uuid.UUID,
) -> QuizSubmissionResponse | None:
    quiz = await session.scalar(
        select(Quiz).where(
            Quiz.id == quiz_id,
            Quiz.tenant_id == tenant_id,
            Quiz.user_id == user_id,
        )
    )
    if quiz is None:
        raise ValueError("Quiz not found for tenant")
    statement = select(QuizSubmission).where(
        QuizSubmission.tenant_id == tenant_id,
        QuizSubmission.quiz_id == quiz_id,
        QuizSubmission.chapter_id == quiz.chapter_id,
    )
    statement = statement.where(QuizSubmission.user_id == user_id)
    submission = await session.scalar(statement.order_by(QuizSubmission.created_at.desc(), QuizSubmission.id.desc()))
    if submission is None:
        return None
    mastery = await get_chapter_mastery(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        chapter_id=quiz.chapter_id,
    )
    if mastery is None:
        raise ValueError("Mastery record not found for tenant")
    results = [QuizQuestionResultResponse(**result) for result in submission.results]
    return build_submission_response(submission=submission, results=results, mastery=mastery)
