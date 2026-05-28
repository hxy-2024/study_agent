import uuid
from types import SimpleNamespace

import pytest

from app.db.models import AgentRunStatus, AgentType, Chapter, MessageRole, SessionStatus
from app.domain.sessions.schemas import MessageCreate, MessageCitationCreate, SessionCreate
from app.domain.sessions.service import (
    answer_session_message,
    build_message_response,
    create_message,
    create_session_for_chapter,
    record_agent_run,
)


def make_chapter(tenant_id: uuid.UUID, study_space_id: uuid.UUID, chapter_id: uuid.UUID) -> Chapter:
    return Chapter(
        id=chapter_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        learning_route_id=uuid.uuid4(),
        order_index=1,
        title="Retrieval basics",
        goal="Understand grounded answers",
        summary="Use citations in answers",
        estimated_days=2,
        source_chunk_refs=[],
    )


@pytest.mark.anyio
async def test_create_session_for_chapter_uses_chapter_context() -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    chapter = make_chapter(tenant_id, study_space_id, chapter_id)
    added = []

    class FakeSession:
        async def scalar(self, _statement):
            return chapter

        def add(self, obj) -> None:
            added.append(obj)

        async def commit(self) -> None:
            pass

        async def refresh(self, obj) -> None:
            if obj.id is None:
                obj.id = uuid.uuid4()

    tutor_session = await create_session_for_chapter(
        session=FakeSession(),
        tenant_id=tenant_id,
        chapter_id=chapter_id,
        payload=SessionCreate(title="First tutoring session"),
    )

    assert tutor_session.status == SessionStatus.active
    assert tutor_session.tenant_id == tenant_id
    assert tutor_session.study_space_id == study_space_id
    assert tutor_session.chapter_id == chapter_id
    assert tutor_session.title == "First tutoring session"


@pytest.mark.anyio
async def test_create_message_persists_citations_after_message_flush() -> None:
    tenant_id = uuid.uuid4()
    tutor_session = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        study_space_id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
    )
    added = []

    class FakeSession:
        async def scalar(self, _statement):
            return tutor_session

        def add(self, obj) -> None:
            added.append(obj)

        async def flush(self) -> None:
            for obj in added:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()

        async def commit(self) -> None:
            pass

        async def refresh(self, _obj) -> None:
            pass

    message = await create_message(
        session=FakeSession(),
        tenant_id=tenant_id,
        session_id=tutor_session.id,
        payload=MessageCreate(
            role=MessageRole.assistant,
            content="Grounded answer",
            citations=[
                MessageCitationCreate(
                    source_id=uuid.uuid4(),
                    source_chunk_id=uuid.uuid4(),
                    quote="Relevant source text",
                    citation={"page": 4},
                )
            ],
        ),
    )

    citation = added[1]
    assert message.role == MessageRole.assistant
    assert message.content == "Grounded answer"
    assert citation.message_id == message.id
    assert citation.tenant_id == tenant_id
    assert citation.quote == "Relevant source text"


@pytest.mark.anyio
async def test_record_agent_run_defaults_to_session_tutor_completed_run() -> None:
    tenant_id = uuid.uuid4()
    tutor_session = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        study_space_id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
    )
    added = []

    class FakeSession:
        async def scalar(self, _statement):
            return tutor_session

        def add(self, obj) -> None:
            added.append(obj)

        async def commit(self) -> None:
            pass

        async def refresh(self, obj) -> None:
            if obj.id is None:
                obj.id = uuid.uuid4()

    run = await record_agent_run(
        session=FakeSession(),
        tenant_id=tenant_id,
        session_id=tutor_session.id,
        input_payload={"question": "Why cite?"},
        output_payload={"answer": "To stay grounded."},
        model="deterministic",
        total_tokens=12,
    )

    assert run.agent_type == AgentType.session_tutor
    assert run.status == AgentRunStatus.completed
    assert run.study_space_id == tutor_session.study_space_id
    assert run.input_payload["question"] == "Why cite?"
    assert run.total_tokens == 12


def test_build_message_response_includes_citations() -> None:
    message_id = uuid.uuid4()
    response = build_message_response(
        message=SimpleNamespace(
            id=message_id,
            session_id=uuid.uuid4(),
            role=MessageRole.assistant,
            content="Answer",
            created_at=None,
        ),
        citations=[
            SimpleNamespace(
                id=uuid.uuid4(),
                message_id=message_id,
                source_id=uuid.uuid4(),
                source_chunk_id=uuid.uuid4(),
                quote="Quoted evidence",
                citation={"page": 2},
            )
        ],
    )

    assert response.role == "assistant"
    assert response.citations[0].quote == "Quoted evidence"


@pytest.mark.anyio
async def test_answer_session_message_delegates_to_graph(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    captured = {}

    async def fake_run_session_tutor_graph(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id=uuid.uuid4(),
            session_id=session_id,
            role="assistant",
            content="Graph answer",
            metadata={},
            citations=[],
            created_at=None,
        )

    monkeypatch.setattr(
        "app.domain.session_tutor_graph.service.run_session_tutor_graph",
        fake_run_session_tutor_graph,
    )

    response = await answer_session_message(
        session=object(),
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        content="Explain graph orchestration.",
        embedding_provider=object(),
        answer_provider=object(),
    )

    assert response.content == "Graph answer"
    assert captured["tenant_id"] == tenant_id
    assert captured["user_id"] == user_id
