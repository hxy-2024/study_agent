import uuid
from types import SimpleNamespace

import pytest

from app.db.models import AgentRun, ChapterMentorState, Message, MessageRole
from app.domain.chapter_mentor.schemas import (
    ChapterMentorCitationResponse,
    ChapterMentorResponse,
)
from app.domain.rag.retrieval import RetrievedChunk
from app.domain.session_tutor_graph.service import run_session_tutor_graph


class FakeEmbeddingProvider:
    dimension = 16

    def embed_text(self, _text: str) -> list[float]:
        return [0.1] * self.dimension


class FakeAnswerProvider:
    def __init__(self) -> None:
        self.web_search_results = None

    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict[uuid.UUID, str],
        web_search_results: list[dict[str, str]] | None = None,
        thinking_effort: str = "medium",
    ) -> ChapterMentorResponse:
        self.web_search_results = web_search_results
        return ChapterMentorResponse(
            question=question,
            answer=f"Grounded answer for: {question}",
            citations=[
                ChapterMentorCitationResponse(
                    source_id=chunks[0].source_id,
                    chunk_id=chunks[0].id,
                    source_filename=source_filenames[chunks[0].source_id],
                    chunk_index=chunks[0].chunk_index,
                    text=chunks[0].text,
                )
            ],
        )


class FailingAnswerProvider:
    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        source_filenames: dict[uuid.UUID, str],
        web_search_results: list[dict[str, str]] | None = None,
        thinking_effort: str = "medium",
    ) -> ChapterMentorResponse:
        raise RuntimeError("provider unavailable")


class FakeWebSearchTool:
    def __init__(self, results: list[dict[str, str]] | None = None) -> None:
        self.calls = []
        self.results = results or []

    async def ainvoke(self, payload: dict) -> list[dict[str, str]]:
        self.calls.append(payload)
        return self.results


@pytest.mark.anyio
async def test_graph_records_messages_agent_run_and_supervision(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    added = []

    tutor_session = SimpleNamespace(
        id=session_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        chapter_id=chapter_id,
    )
    mentor_state = ChapterMentorState(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        chapter_id=chapter_id,
        summary="Learner needs citation practice.",
        weak_points=["Citation grounding"],
        next_actions=["Review cited chunks"],
        evidence=[],
        source_session_count=1,
        source_message_count=2,
    )
    retrieved = [
        RetrievedChunk(
            id=chunk_id,
            tenant_id=tenant_id,
            study_space_id=study_space_id,
            source_id=source_id,
            chunk_index=0,
            text="Evidence text",
            citation={"source_filename": "notes.md", "chunk_index": 0},
            embedding=[0.1] * 16,
            score=0.91,
        )
    ]

    class FakeSession:
        async def scalar(self, statement):
            if "chapter_mentor_states" in str(statement):
                return mentor_state
            return tutor_session

        def add(self, obj) -> None:
            added.append(obj)

        async def flush(self) -> None:
            for obj in added:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()

        async def commit(self) -> None:
            pass

        async def refresh(self, obj) -> None:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def fake_retrieve_chunks(**kwargs):
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["study_space_id"] == study_space_id
        return retrieved

    async def fake_load_source_filenames(**kwargs):
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["study_space_id"] == study_space_id
        return {source_id: "notes.md"}

    monkeypatch.setattr(
        "app.domain.session_tutor_graph.nodes.retrieve_chunks",
        fake_retrieve_chunks,
    )
    monkeypatch.setattr(
        "app.domain.session_tutor_graph.nodes.load_source_filenames",
        fake_load_source_filenames,
    )

    fake_web_search = FakeWebSearchTool(
        [
            {
                "title": "Citation practice",
                "url": "https://example.test/citation",
                "snippet": "Fresh context about citation practice.",
            }
        ]
    )
    answer_provider = FakeAnswerProvider()
    monkeypatch.setattr(
        "app.domain.session_tutor_graph.nodes.web_search_tool",
        fake_web_search,
    )

    response = await run_session_tutor_graph(
        session=FakeSession(),
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        content="I am confused about citations.",
        embedding_provider=FakeEmbeddingProvider(),
        answer_provider=answer_provider,
        web_search_enabled=True,
    )

    messages = [obj for obj in added if isinstance(obj, Message)]
    runs = [obj for obj in added if isinstance(obj, AgentRun)]
    assert response.content == "Grounded answer for: I am confused about citations."
    assert len(messages) == 2
    assert messages[0].role == MessageRole.user
    assert messages[1].role == MessageRole.assistant
    assert len(runs) == 1
    assert runs[0].output_payload["graph_name"] == "session_tutor"
    assert runs[0].output_payload["thread_id"] == f"session:{session_id}"
    assert runs[0].output_payload["checkpoint_backend"] == "memory"
    assert runs[0].output_payload["state_schema_version"] == 1
    assert runs[0].output_payload["node_trace"][-1] == "record_agent_run"
    assert runs[0].input_payload["web_search_enabled"] is True
    assert "web_search" in runs[0].output_payload["node_trace"]
    assert runs[0].output_payload["web_search_result_count"] == 1
    assert runs[0].output_payload["web_search_error"] is None
    assert fake_web_search.calls == [
        {
            "query": "I am confused about citations.",
            "max_results": 3,
            "timeout_seconds": 5,
        }
    ]
    assert answer_provider.web_search_results == [
        {
            "title": "Citation practice",
            "url": "https://example.test/citation",
            "snippet": "Fresh context about citation practice.",
        }
    ]
    assert runs[0].output_payload["chapter_supervision_used"] is True
    assert any(
        signal["type"] == "confusion_detected"
        for signal in runs[0].output_payload["learning_signals"]
    )


@pytest.mark.anyio
async def test_graph_records_failed_agent_run_after_user_message(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    added = []

    tutor_session = SimpleNamespace(
        id=session_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        chapter_id=chapter_id,
    )

    class FakeSession:
        async def scalar(self, statement):
            if "chapter_mentor_states" in str(statement):
                return None
            return tutor_session

        def add(self, obj) -> None:
            added.append(obj)

        async def flush(self) -> None:
            for obj in added:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()

        async def commit(self) -> None:
            pass

        async def refresh(self, obj) -> None:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def fake_retrieve_chunks(**_kwargs):
        return []

    async def fake_load_source_filenames(**_kwargs):
        return {}

    monkeypatch.setattr(
        "app.domain.session_tutor_graph.nodes.retrieve_chunks",
        fake_retrieve_chunks,
    )
    monkeypatch.setattr(
        "app.domain.session_tutor_graph.nodes.load_source_filenames",
        fake_load_source_filenames,
    )
    monkeypatch.setattr(
        "app.domain.session_tutor_graph.nodes.web_search_tool",
        FakeWebSearchTool(),
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await run_session_tutor_graph(
            session=FakeSession(),
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            content="Explain failure handling.",
            embedding_provider=FakeEmbeddingProvider(),
            answer_provider=FailingAnswerProvider(),
        )

    messages = [obj for obj in added if isinstance(obj, Message)]
    runs = [obj for obj in added if isinstance(obj, AgentRun)]
    assert len(messages) == 1
    assert messages[0].role == MessageRole.user
    assert len(runs) == 1
    assert runs[0].status.value == "failed"
    assert runs[0].error_message == "provider unavailable"
    assert runs[0].input_payload["graph_name"] == "session_tutor"
    assert runs[0].input_payload["thread_id"] == f"session:{session_id}"
    assert runs[0].input_payload["checkpoint_backend"] == "memory"
    assert runs[0].input_payload["state_schema_version"] == 1
    assert runs[0].input_payload["content"] == "Explain failure handling."
    assert runs[0].input_payload["user_message_id"] == str(messages[0].id)
    assert runs[0].input_payload["node_trace"] == [
        "load_session_context",
        "persist_user_message",
        "load_chapter_supervision",
        "retrieve_evidence",
        "web_search",
        "generate_answer",
    ]


@pytest.mark.anyio
async def test_graph_rolls_back_before_recording_failed_agent_run_after_db_error(
    monkeypatch,
) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    added = []

    tutor_session = SimpleNamespace(
        id=session_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        chapter_id=chapter_id,
    )
    retrieved = [
        RetrievedChunk(
            id=chunk_id,
            tenant_id=tenant_id,
            study_space_id=study_space_id,
            source_id=source_id,
            chunk_index=0,
            text="Evidence text",
            citation={"source_filename": "notes.md", "chunk_index": 0},
            embedding=[0.1] * 16,
            score=0.91,
        )
    ]

    class RollbackRequiredSession:
        def __init__(self) -> None:
            self.commit_count = 0
            self.needs_rollback = False
            self.rollback_calls = 0

        async def scalar(self, statement):
            if self.needs_rollback:
                raise RuntimeError("rollback required")
            if "chapter_mentor_states" in str(statement):
                return None
            return tutor_session

        def add(self, obj) -> None:
            if self.needs_rollback:
                raise RuntimeError("rollback required")
            added.append(obj)

        async def flush(self) -> None:
            if self.needs_rollback:
                raise RuntimeError("rollback required")
            for obj in added:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()

        async def commit(self) -> None:
            if self.needs_rollback:
                raise RuntimeError("rollback required")
            self.commit_count += 1
            if self.commit_count == 2:
                self.needs_rollback = True
                raise RuntimeError("assistant write failed")

        async def refresh(self, obj) -> None:
            if self.needs_rollback:
                raise RuntimeError("rollback required")
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

        async def rollback(self) -> None:
            self.rollback_calls += 1
            self.needs_rollback = False

    async def fake_retrieve_chunks(**kwargs):
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["study_space_id"] == study_space_id
        return retrieved

    async def fake_load_source_filenames(**kwargs):
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["study_space_id"] == study_space_id
        return {source_id: "notes.md"}

    monkeypatch.setattr(
        "app.domain.session_tutor_graph.nodes.retrieve_chunks",
        fake_retrieve_chunks,
    )
    monkeypatch.setattr(
        "app.domain.session_tutor_graph.nodes.load_source_filenames",
        fake_load_source_filenames,
    )
    monkeypatch.setattr(
        "app.domain.session_tutor_graph.nodes.web_search_tool",
        FakeWebSearchTool(),
    )

    fake_session = RollbackRequiredSession()
    with pytest.raises(RuntimeError, match="assistant write failed"):
        await run_session_tutor_graph(
            session=fake_session,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            content="Explain rollback handling.",
            embedding_provider=FakeEmbeddingProvider(),
            answer_provider=FakeAnswerProvider(),
        )

    messages = [obj for obj in added if isinstance(obj, Message)]
    runs = [obj for obj in added if isinstance(obj, AgentRun)]
    assert fake_session.rollback_calls == 1
    assert len(messages) == 2
    assert messages[0].role == MessageRole.user
    assert messages[1].role == MessageRole.assistant
    assert len(runs) == 1
    assert runs[0].status.value == "failed"
    assert runs[0].error_message == "assistant write failed"
    assert runs[0].input_payload["content"] == "Explain rollback handling."
    assert runs[0].input_payload["user_message_id"] == str(messages[0].id)
