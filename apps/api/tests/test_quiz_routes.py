import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes_quizzes
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.quizzes.schemas import (
    MasteryRecordResponse,
    QuizEvidenceResponse,
    QuizQuestionResponse,
    QuizQuestionResultResponse,
    QuizResponse,
    QuizSubmissionResponse,
)
from app.main import app


async def fake_get_db_session() -> AsyncGenerator[object, None]:
    yield object()


def quiz_fixture(chapter_id: uuid.UUID, quiz_id: uuid.UUID | None = None) -> QuizResponse:
    return QuizResponse(
        id=quiz_id or uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        chapter_id=chapter_id,
        title="Retrieval Quiz",
        status="active",
        generation_strategy="deterministic",
        question_count=1,
        questions=[
            QuizQuestionResponse(
                id=uuid.uuid4(),
                order_index=1,
                prompt="Which option is grounded?",
                options=["A", "B", "C", "D"],
                evidence=QuizEvidenceResponse(source_filename="rag.md", chunk_index=1, text="Evidence"),
            )
        ],
    )


def mastery_fixture(chapter_id: uuid.UUID, submission_id: uuid.UUID | None = None) -> MasteryRecordResponse:
    return MasteryRecordResponse(
        id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        chapter_id=chapter_id,
        score_percent=100,
        level="mastered",
        weak_points=[],
        last_quiz_submission_id=submission_id or uuid.uuid4(),
    )


def submission_fixture(
    quiz_id: uuid.UUID,
    chapter_id: uuid.UUID,
    user_id: uuid.UUID,
) -> QuizSubmissionResponse:
    submission_id = uuid.uuid4()
    return QuizSubmissionResponse(
        id=submission_id,
        quiz_id=quiz_id,
        chapter_id=chapter_id,
        user_id=user_id,
        answers=[0],
        score_percent=100,
        correct_count=1,
        question_count=1,
        results=[
            QuizQuestionResultResponse(
                question_id=uuid.uuid4(),
                order_index=1,
                prompt="Which option is grounded?",
                selected_option_index=0,
                correct_option_index=0,
                is_correct=True,
                explanation="Because evidence supports it.",
                evidence=QuizEvidenceResponse(),
            )
        ],
        weak_points=[],
        mastery=mastery_fixture(chapter_id=chapter_id, submission_id=submission_id),
    )


@pytest.mark.anyio
async def test_generate_quiz_uses_authorized_tenant_and_optional_body(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_generate_chapter_quiz(**kwargs):
        captured.update(kwargs)
        return quiz_fixture(chapter_id=chapter_id)

    monkeypatch.setattr(routes_quizzes, "generate_chapter_quiz", fake_generate_chapter_quiz)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/chapters/{chapter_id}/quizzes/generate",
                json={"question_count": 4},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert captured["tenant_id"] == tenant_id
    assert captured["user_id"] == user_id
    assert captured["chapter_id"] == chapter_id
    assert captured["question_count"] == 4
    assert response.json()["title"] == "Retrieval Quiz"


@pytest.mark.anyio
async def test_generate_quiz_defaults_body_and_rejects_client_tenant(monkeypatch) -> None:
    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/chapters/{uuid.uuid4()}/quizzes/generate",
                json={"tenant_id": str(uuid.uuid4()), "question_count": 3},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_quiz_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quiz_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_get_quiz(**kwargs):
        captured.update(kwargs)
        return quiz_fixture(chapter_id=chapter_id, quiz_id=quiz_id)

    monkeypatch.setattr(routes_quizzes, "get_quiz", fake_get_quiz)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/quizzes/{quiz_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["user_id"] == user_id
    assert captured["quiz_id"] == quiz_id
    assert response.json()["id"] == str(quiz_id)


@pytest.mark.anyio
async def test_retake_quiz_uses_authorized_tenant_and_user(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quiz_id = uuid.uuid4()
    new_quiz_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_retake_quiz(**kwargs):
        captured.update(kwargs)
        return quiz_fixture(chapter_id=chapter_id, quiz_id=new_quiz_id)

    monkeypatch.setattr(routes_quizzes, "retake_quiz", fake_retake_quiz)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/quizzes/{quiz_id}/retake")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert captured["tenant_id"] == tenant_id
    assert captured["user_id"] == user_id
    assert captured["quiz_id"] == quiz_id
    assert response.json()["id"] == str(new_quiz_id)
    assert response.json()["chapter_id"] == str(chapter_id)


@pytest.mark.anyio
async def test_submit_quiz_uses_authorized_tenant_and_user(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quiz_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_submit_quiz_answers(**kwargs):
        captured.update(kwargs)
        return submission_fixture(quiz_id=quiz_id, chapter_id=chapter_id, user_id=user_id)

    monkeypatch.setattr(routes_quizzes, "submit_quiz_answers", fake_submit_quiz_answers)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/quizzes/{quiz_id}/submit", json={"answers": [0]})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["user_id"] == user_id
    assert captured["quiz_id"] == quiz_id
    assert captured["answers"] == [0]
    assert response.json()["user_id"] == str(user_id)


@pytest.mark.anyio
async def test_get_quiz_result_uses_authorized_scope(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quiz_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_get_latest_quiz_result(**kwargs):
        captured.update(kwargs)
        return submission_fixture(quiz_id=quiz_id, chapter_id=quiz_id, user_id=user_id)

    monkeypatch.setattr(routes_quizzes, "get_latest_quiz_result", fake_get_latest_quiz_result)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/quizzes/{quiz_id}/result")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["quiz_id"] == quiz_id
    assert captured["user_id"] == user_id
    assert response.json()["quiz_id"] == str(quiz_id)


@pytest.mark.anyio
async def test_get_chapter_mastery_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_get_chapter_mastery(**kwargs):
        captured.update(kwargs)
        return mastery_fixture(chapter_id=chapter_id)

    monkeypatch.setattr(routes_quizzes, "get_chapter_mastery", fake_get_chapter_mastery)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/chapters/{chapter_id}/mastery")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["user_id"] == user_id
    assert captured["chapter_id"] == chapter_id
    assert response.json()["level"] == "mastered"


@pytest.mark.anyio
async def test_quiz_answer_errors_map_to_400(monkeypatch) -> None:
    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_submit_quiz_answers(**kwargs):
        raise ValueError("Quiz answer count does not match question count")

    monkeypatch.setattr(routes_quizzes, "submit_quiz_answers", fake_submit_quiz_answers)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/quizzes/{uuid.uuid4()}/submit", json={"answers": [0]})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.anyio
async def test_quiz_not_found_errors_map_to_404(monkeypatch) -> None:
    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_get_quiz(**kwargs):
        raise ValueError("Quiz not found for tenant")

    monkeypatch.setattr(routes_quizzes, "get_quiz", fake_get_quiz)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/quizzes/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
