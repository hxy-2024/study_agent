import uuid
from types import SimpleNamespace

import pytest

from app.db.models import (
    Chapter,
    ChapterMentorState,
    LearningRoute,
    LearningRouteStatus,
    MasteryLevel,
    MasteryRecord,
    Quiz,
    QuizQuestion,
    QuizStatus,
    Source,
    SourceChunk,
    SourceStatus,
    StudySpace,
)
from app.domain.quizzes.service import (
    calculate_mastery_level,
    generate_chapter_quiz,
    get_latest_quiz_result,
    get_quiz,
    submit_quiz_answers,
    validate_answers,
)


def make_chapter_context(question_count: int = 3):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space = StudySpace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        owner_user_id=user_id,
        name="Vector Search",
        goal="Learn RAG",
        level="beginner",
        intensity="normal",
        target_days=7,
        status=None,
    )
    route = LearningRoute(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        study_space_id=study_space.id,
        version=1,
        status=LearningRouteStatus.active,
        title="RAG Route",
        summary="Learn retrieval",
    )
    chunk_ids = [uuid.uuid4() for _ in range(question_count)]
    chapter = Chapter(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        study_space_id=study_space.id,
        learning_route_id=route.id,
        order_index=1,
        title="Retrieval Basics",
        goal="Understand chunking and retrieval.",
        summary="Chunk documents, embed them, and retrieve relevant context.",
        estimated_days=2,
        source_chunk_refs=[{"chunk_id": str(chunk_id)} for chunk_id in chunk_ids],
    )
    source = Source(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        study_space_id=study_space.id,
        filename="rag.md",
        content_type="text/markdown",
        object_key="sources/rag.md",
        status=SourceStatus.ready,
    )
    chunks = [
        SourceChunk(
            id=chunk_id,
            tenant_id=tenant_id,
            study_space_id=study_space.id,
            source_id=source.id,
            chunk_index=index,
            text=f"Evidence {index}: retrieval uses embeddings and citations for grounded answers.",
            token_count=12,
            citation={"page_number": index + 1},
            embedding=[0.1] * 16,
            is_active=True,
        )
        for index, chunk_id in enumerate(chunk_ids)
    ]
    mentor_state = ChapterMentorState(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        study_space_id=study_space.id,
        chapter_id=chapter.id,
        summary="The learner is unsure about citations.",
        weak_points=["Needs practice with citations"],
        next_actions=[],
        evidence=[],
        source_session_count=1,
        source_message_count=2,
    )
    return SimpleNamespace(
        tenant_id=tenant_id,
        user_id=user_id,
        study_space=study_space,
        route=route,
        chapter=chapter,
        source=source,
        chunks=chunks,
        mentor_state=mentor_state,
    )


class FakeQuizSession:
    def __init__(self, context) -> None:
        self.context = context
        self.added = []
        self.commits = 0
        self.refreshed = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj) -> None:
        self.refreshed.append(obj)


def generated_quiz_from_session(session: FakeQuizSession) -> Quiz:
    return next(obj for obj in session.added if isinstance(obj, Quiz))


def generated_questions_from_session(session: FakeQuizSession) -> list[QuizQuestion]:
    return [obj for obj in session.added if isinstance(obj, QuizQuestion)]


@pytest.mark.anyio
async def test_generate_chapter_quiz_creates_default_deterministic_questions(monkeypatch) -> None:
    context = make_chapter_context(question_count=3)
    session = FakeQuizSession(context)

    async def fake_ensure_chapter_for_quiz(**kwargs):
        return context.chapter

    async def fake_load_chapter_quiz_evidence(**kwargs):
        return [(chunk, context.source) for chunk in context.chunks]

    async def fake_load_chapter_mentor_summary(**kwargs):
        return context.mentor_state

    monkeypatch.setattr("app.domain.quizzes.service.ensure_chapter_for_quiz", fake_ensure_chapter_for_quiz)
    monkeypatch.setattr("app.domain.quizzes.service.load_chapter_quiz_evidence", fake_load_chapter_quiz_evidence)
    monkeypatch.setattr("app.domain.quizzes.service.load_chapter_mentor_summary", fake_load_chapter_mentor_summary)

    response = await generate_chapter_quiz(
        session=session,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        chapter_id=context.chapter.id,
    )

    quiz = generated_quiz_from_session(session)
    questions = generated_questions_from_session(session)
    assert quiz.status == QuizStatus.active
    assert quiz.user_id == context.user_id
    assert quiz.question_count == 3
    assert len(questions) == 3
    assert all(len(question.options) == 4 for question in questions)
    assert all(not option.startswith("Use chapter evidence") for question in questions for option in question.options)
    assert [question.correct_option_index for question in questions] == [0, 3, 2]
    correct_options = [question.options[question.correct_option_index] for question in questions]
    assert correct_options == [
        "Start from the chapter goal, then verify claims against the linked evidence.",
        "Use the citation text as the anchor for the answer.",
        "Turn the weak point into a targeted review question.",
    ]
    assert [question.order_index for question in questions] == [1, 2, 3]
    assert response.id == quiz.id
    assert len(response.questions) == 3
    assert not hasattr(response.questions[0], "correct_option_index")
    assert session.commits == 1


@pytest.mark.anyio
async def test_generate_chapter_quiz_honors_requested_question_count(monkeypatch) -> None:
    context = make_chapter_context(question_count=5)
    session = FakeQuizSession(context)

    async def fake_ensure_chapter_for_quiz(**kwargs):
        return context.chapter

    async def fake_load_chapter_quiz_evidence(**kwargs):
        return [(chunk, context.source) for chunk in context.chunks]

    async def fake_load_chapter_mentor_summary(**kwargs):
        return None

    monkeypatch.setattr("app.domain.quizzes.service.ensure_chapter_for_quiz", fake_ensure_chapter_for_quiz)
    monkeypatch.setattr("app.domain.quizzes.service.load_chapter_quiz_evidence", fake_load_chapter_quiz_evidence)
    monkeypatch.setattr("app.domain.quizzes.service.load_chapter_mentor_summary", fake_load_chapter_mentor_summary)

    response = await generate_chapter_quiz(
        session=session,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        chapter_id=context.chapter.id,
        question_count=5,
    )

    assert generated_quiz_from_session(session).question_count == 5
    assert len(generated_questions_from_session(session)) == 5
    assert len(response.questions) == 5


def test_calculate_mastery_level_uses_expected_thresholds() -> None:
    assert calculate_mastery_level(0) == MasteryLevel.new
    assert calculate_mastery_level(39) == MasteryLevel.new
    assert calculate_mastery_level(40) == MasteryLevel.developing
    assert calculate_mastery_level(69) == MasteryLevel.developing
    assert calculate_mastery_level(70) == MasteryLevel.proficient
    assert calculate_mastery_level(89) == MasteryLevel.proficient
    assert calculate_mastery_level(90) == MasteryLevel.mastered


def test_validate_answers_rejects_wrong_count_and_out_of_range() -> None:
    questions = [
        QuizQuestion(options=["A", "B", "C", "D"], correct_option_index=1),
        QuizQuestion(options=["A", "B", "C", "D"], correct_option_index=2),
    ]

    with pytest.raises(ValueError, match="answer count"):
        validate_answers(questions=questions, answers=[1])

    with pytest.raises(ValueError, match="out of range"):
        validate_answers(questions=questions, answers=[1, 4])


@pytest.mark.anyio
async def test_submit_quiz_answers_scores_submission_and_upserts_mastery(monkeypatch) -> None:
    context = make_chapter_context(question_count=3)
    quiz = Quiz(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        study_space_id=context.study_space.id,
        chapter_id=context.chapter.id,
        title="Retrieval Basics Quiz",
        status=QuizStatus.active,
        question_count=3,
    )
    questions = [
        QuizQuestion(
            id=uuid.uuid4(),
            tenant_id=context.tenant_id,
            quiz_id=quiz.id,
            chapter_id=context.chapter.id,
            order_index=index,
            prompt=f"Question {index}",
            options=["A", "B", "C", "D"],
            correct_option_index=correct,
            explanation=f"Explanation {index}",
            evidence={"chunk_id": str(context.chunks[index - 1].id)},
        )
        for index, correct in enumerate([0, 1, 2], start=1)
    ]
    session = FakeQuizSession(context)
    mastery_call_order = []

    async def fake_load_quiz_with_questions(**kwargs):
        assert kwargs["for_update"] is True
        return quiz, questions

    async def fake_get_chapter_mastery(**kwargs):
        mastery_call_order.append("get")
        return None

    async def fake_lock_chapter_mastery_scope(**kwargs):
        mastery_call_order.append("lock")
        return None

    monkeypatch.setattr("app.domain.quizzes.service.load_quiz_with_questions", fake_load_quiz_with_questions)
    monkeypatch.setattr("app.domain.quizzes.service.get_chapter_mastery", fake_get_chapter_mastery)
    monkeypatch.setattr("app.domain.quizzes.service.lock_chapter_mastery_scope", fake_lock_chapter_mastery_scope)

    response = await submit_quiz_answers(
        session=session,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        quiz_id=quiz.id,
        answers=[0, 3, 2],
    )

    submission = next(obj for obj in session.added if obj.__class__.__name__ == "QuizSubmission")
    mastery = next(obj for obj in session.added if isinstance(obj, MasteryRecord))
    assert submission.score_percent == 67
    assert submission.correct_count == 2
    assert submission.question_count == 3
    assert quiz.status == QuizStatus.submitted
    assert mastery.level == MasteryLevel.developing
    assert mastery.score_percent == 67
    assert mastery.last_quiz_submission_id == submission.id
    assert response.score_percent == 67
    assert response.mastery.level == "developing"
    assert response.results[1].correct_option_index == 1
    assert response.results[1].explanation == "Explanation 2"
    result_evidence = response.results[1].evidence.model_dump()
    assert result_evidence == {
        "source_filename": None,
        "chunk_index": None,
        "text": None,
    }
    assert session.commits == 1
    assert mastery_call_order == ["lock", "get"]


@pytest.mark.anyio
async def test_submit_quiz_answers_updates_existing_mastery(monkeypatch) -> None:
    context = make_chapter_context(question_count=1)
    quiz = Quiz(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        study_space_id=context.study_space.id,
        chapter_id=context.chapter.id,
        title="Retrieval Basics Quiz",
        status=QuizStatus.active,
        question_count=1,
    )
    question = QuizQuestion(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        quiz_id=quiz.id,
        chapter_id=context.chapter.id,
        order_index=1,
            prompt="Question",
            options=["A", "B", "C", "D"],
            correct_option_index=0,
            explanation="Correct",
            evidence={
                "chunk_id": str(uuid.uuid4()),
                "source_id": str(uuid.uuid4()),
                "source_filename": "rag.md",
                "chunk_index": 2,
                "citation": {"page_number": 7},
                "text": "Use cited evidence.",
            },
        )
    existing_mastery = MasteryRecord(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        study_space_id=context.study_space.id,
        chapter_id=context.chapter.id,
        score_percent=40,
        level=MasteryLevel.developing,
        weak_points=["old"],
        last_quiz_submission_id=uuid.uuid4(),
    )
    session = FakeQuizSession(context)

    async def fake_load_quiz_with_questions(**kwargs):
        assert kwargs["for_update"] is True
        return quiz, [question]

    async def fake_get_chapter_mastery(**kwargs):
        return existing_mastery

    async def fake_lock_chapter_mastery_scope(**kwargs):
        return None

    monkeypatch.setattr("app.domain.quizzes.service.load_quiz_with_questions", fake_load_quiz_with_questions)
    monkeypatch.setattr("app.domain.quizzes.service.get_chapter_mastery", fake_get_chapter_mastery)
    monkeypatch.setattr("app.domain.quizzes.service.lock_chapter_mastery_scope", fake_lock_chapter_mastery_scope)

    response = await submit_quiz_answers(
        session=session,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        quiz_id=quiz.id,
        answers=[0],
    )

    submission = next(obj for obj in session.added if obj.__class__.__name__ == "QuizSubmission")
    assert existing_mastery.score_percent == 100
    assert existing_mastery.level == MasteryLevel.mastered
    assert existing_mastery.last_quiz_submission_id == submission.id
    assert response.mastery.id == existing_mastery.id


@pytest.mark.anyio
async def test_submit_quiz_answers_rejects_resubmission(monkeypatch) -> None:
    context = make_chapter_context(question_count=1)
    quiz = Quiz(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        study_space_id=context.study_space.id,
        chapter_id=context.chapter.id,
        title="Retrieval Basics Quiz",
        status=QuizStatus.submitted,
        question_count=1,
    )
    question = QuizQuestion(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        quiz_id=quiz.id,
        chapter_id=context.chapter.id,
        order_index=1,
        prompt="Question",
        options=["A", "B", "C", "D"],
        correct_option_index=0,
        explanation="Correct",
        evidence={},
    )
    session = FakeQuizSession(context)

    async def fake_load_quiz_with_questions(**kwargs):
        assert kwargs["for_update"] is True
        return quiz, [question]

    monkeypatch.setattr("app.domain.quizzes.service.load_quiz_with_questions", fake_load_quiz_with_questions)

    with pytest.raises(ValueError, match="already submitted"):
        await submit_quiz_answers(
            session=session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            quiz_id=quiz.id,
            answers=[0],
        )

    assert session.added == []


@pytest.mark.anyio
async def test_get_quiz_does_not_return_correct_answers(monkeypatch) -> None:
    context = make_chapter_context(question_count=1)
    quiz = Quiz(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        study_space_id=context.study_space.id,
        chapter_id=context.chapter.id,
        title="Retrieval Basics Quiz",
        status=QuizStatus.active,
        question_count=1,
    )
    question = QuizQuestion(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        quiz_id=quiz.id,
        chapter_id=context.chapter.id,
        order_index=1,
        prompt="Question",
        options=["A", "B", "C", "D"],
        correct_option_index=0,
        explanation="Correct",
        evidence={
            "chunk_id": str(uuid.uuid4()),
            "source_id": str(uuid.uuid4()),
            "source_filename": "rag.md",
            "chunk_index": 2,
            "citation": {"page_number": 7},
            "text": "Use cited evidence.",
        },
    )

    async def fake_load_quiz_with_questions(**kwargs):
        return quiz, [question]

    monkeypatch.setattr("app.domain.quizzes.service.load_quiz_with_questions", fake_load_quiz_with_questions)

    response = await get_quiz(
        session=FakeQuizSession(context),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        quiz_id=quiz.id,
    )

    dumped = response.model_dump()
    assert "correct_option_index" not in dumped["questions"][0]
    assert "explanation" not in dumped["questions"][0]
    assert "chunk_id" not in dumped["questions"][0]["evidence"]
    assert "source_id" not in dumped["questions"][0]["evidence"]
    assert "citation" not in dumped["questions"][0]["evidence"]
    assert dumped["questions"][0]["evidence"] == {
        "source_filename": "rag.md",
        "chunk_index": 2,
        "text": "Use cited evidence.",
    }


@pytest.mark.anyio
async def test_get_latest_quiz_result_uses_quiz_id(monkeypatch) -> None:
    context = make_chapter_context(question_count=1)
    quiz = Quiz(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        study_space_id=context.study_space.id,
        chapter_id=context.chapter.id,
        title="Retrieval Basics Quiz",
        status=QuizStatus.submitted,
        question_count=1,
    )
    submission = SimpleNamespace(
        id=uuid.uuid4(),
        quiz_id=quiz.id,
        chapter_id=context.chapter.id,
        user_id=context.user_id,
        answers=[0],
        score_percent=100,
        correct_count=1,
        question_count=1,
        results=[
            {
                "question_id": str(uuid.uuid4()),
                "order_index": 1,
                "prompt": "Question",
                "selected_option_index": 0,
                "correct_option_index": 0,
                "is_correct": True,
                "explanation": "Correct",
                "evidence": {},
            }
        ],
        weak_points=[],
        created_at=None,
    )
    mastery = MasteryRecord(
        id=uuid.uuid4(),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        study_space_id=context.study_space.id,
        chapter_id=context.chapter.id,
        score_percent=100,
        level=MasteryLevel.mastered,
        weak_points=[],
        last_quiz_submission_id=submission.id,
    )

    class FakeResultSession:
        def __init__(self) -> None:
            self.scalar_calls = 0

        async def scalar(self, _statement):
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return quiz
            if self.scalar_calls == 2:
                return submission
            return mastery

    result = await get_latest_quiz_result(
        session=FakeResultSession(),
        tenant_id=context.tenant_id,
        quiz_id=quiz.id,
        user_id=context.user_id,
    )

    assert result is not None
    assert result.quiz_id == quiz.id
    assert result.chapter_id == context.chapter.id
    assert result.mastery.level == "mastered"
