# Session Tutor LangGraph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing Session Tutor answer flow into a LangGraph-backed L3 execution agent while preserving the current API response contract.

**Architecture:** Add a small shared agent runtime module and a focused `session_tutor_graph` domain module. Keep existing routes unchanged; `answer_session_message()` remains the compatibility boundary and delegates to the graph when enabled. The graph reads optional Chapter Mentor state as L2 supervision context and records L1-ready learning signals in `agent_runs.output_payload`.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, LangGraph Python, existing RAG retrieval, existing answer providers, pytest, ruff.

---

## Scope

Implement:

- API dependency additions for LangGraph.
- Runtime configuration for enabling/disabling graph execution.
- Session Tutor graph state, nodes, graph builder, and runner.
- Existing `answer_session_message()` delegation to the graph.
- Tests for graph state, supervision context, successful persistence, failure recording, and route compatibility.
- README/API documentation notes for the graph-backed tutor.

Do not implement:

- SSE streaming.
- Full L1/L2/L3 parent graph.
- Postgres checkpoint migrations.
- Background workers.
- Automatic Space Planner reruns.
- Route mutation or planner action mutation from Session Tutor.

## File Structure

Modify:

- `apps/api/pyproject.toml`
- `apps/api/app/core/config.py`
- `apps/api/app/domain/sessions/service.py`
- `apps/api/README.md`
- `README.md` if local setup commands need dependency notes.

Create:

- `apps/api/app/domain/agent_runtime/__init__.py`
- `apps/api/app/domain/agent_runtime/config.py`
- `apps/api/app/domain/agent_runtime/state.py`
- `apps/api/app/domain/session_tutor_graph/__init__.py`
- `apps/api/app/domain/session_tutor_graph/state.py`
- `apps/api/app/domain/session_tutor_graph/nodes.py`
- `apps/api/app/domain/session_tutor_graph/graph.py`
- `apps/api/app/domain/session_tutor_graph/service.py`
- `apps/api/tests/test_agent_runtime_config.py`
- `apps/api/tests/test_session_tutor_graph_state.py`
- `apps/api/tests/test_session_tutor_graph_service.py`

---

### Task 1: Add Runtime Configuration and Dependencies

**Files:**

- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/app/core/config.py`
- Create: `apps/api/app/domain/agent_runtime/__init__.py`
- Create: `apps/api/app/domain/agent_runtime/config.py`
- Create: `apps/api/app/domain/agent_runtime/state.py`
- Test: `apps/api/tests/test_agent_runtime_config.py`

- [ ] **Step 1: Add failing config tests**

Create `apps/api/tests/test_agent_runtime_config.py`:

```python
from app.core.config import Settings
from app.domain.agent_runtime.config import graph_runtime_config_from_settings


def test_graph_runtime_config_defaults_to_enabled_memory_backend() -> None:
    settings = Settings()

    config = graph_runtime_config_from_settings(settings)

    assert config.session_tutor_graph_enabled is True
    assert config.checkpoint_backend == "memory"


def test_graph_runtime_config_accepts_none_checkpoint_backend() -> None:
    settings = Settings(session_tutor_graph_checkpoint_backend="none")

    config = graph_runtime_config_from_settings(settings)

    assert config.checkpoint_backend == "none"
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
cd F:\AIproject\study_agent\apps\api
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_agent_runtime_config.py -q
```

Expected: fail because `app.domain.agent_runtime` does not exist.

- [ ] **Step 3: Add dependencies**

Run:

```powershell
cd F:\AIproject\study_agent\apps\api
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv add langgraph langgraph-checkpoint-postgres "psycopg[binary,pool]"
```

If dependency download is blocked, ask the user to run the same command manually from `apps/api`.

- [ ] **Step 4: Add settings fields**

In `apps/api/app/core/config.py`, add fields to `Settings`:

```python
session_tutor_graph_enabled: bool = True
session_tutor_graph_checkpoint_backend: str = "memory"
```

- [ ] **Step 5: Add runtime config module**

Create `apps/api/app/domain/agent_runtime/__init__.py`:

```python
"""Shared agent runtime primitives."""
```

Create `apps/api/app/domain/agent_runtime/config.py`:

```python
from dataclasses import dataclass

from app.core.config import Settings


SUPPORTED_CHECKPOINT_BACKENDS = {"memory", "none", "postgres"}


@dataclass(frozen=True)
class GraphRuntimeConfig:
    session_tutor_graph_enabled: bool
    checkpoint_backend: str


def graph_runtime_config_from_settings(settings: Settings) -> GraphRuntimeConfig:
    backend = settings.session_tutor_graph_checkpoint_backend.strip().lower()
    if backend not in SUPPORTED_CHECKPOINT_BACKENDS:
        raise ValueError("Unsupported graph checkpoint backend")
    return GraphRuntimeConfig(
        session_tutor_graph_enabled=settings.session_tutor_graph_enabled,
        checkpoint_backend=backend,
    )
```

Create `apps/api/app/domain/agent_runtime/state.py`:

```python
from typing import Literal, TypedDict


LearningSignalType = Literal[
    "confusion_detected",
    "needs_review",
    "evidence_used",
    "chapter_supervision_used",
]


class LearningSignal(TypedDict):
    type: LearningSignalType
    value: bool
    rationale: str
```

- [ ] **Step 6: Verify task**

Run:

```powershell
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_agent_runtime_config.py -q
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m ruff check app/core/config.py app/domain/agent_runtime tests/test_agent_runtime_config.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/app/core/config.py apps/api/app/domain/agent_runtime apps/api/tests/test_agent_runtime_config.py
git commit -m "feat: add agent runtime config"
```

---

### Task 2: Define Session Tutor Graph State and Learning Signals

**Files:**

- Create: `apps/api/app/domain/session_tutor_graph/__init__.py`
- Create: `apps/api/app/domain/session_tutor_graph/state.py`
- Test: `apps/api/tests/test_session_tutor_graph_state.py`

- [ ] **Step 1: Add failing state tests**

Create `apps/api/tests/test_session_tutor_graph_state.py`:

```python
import uuid

from app.domain.session_tutor_graph.state import (
    ChapterSupervision,
    SessionTutorGraphState,
    build_learning_signals,
)


def test_build_learning_signals_detects_confusion_and_evidence() -> None:
    signals = build_learning_signals(
        content="I am confused about citations.",
        citation_count=2,
        chapter_supervision=ChapterSupervision(
            summary="Needs stronger evidence use.",
            weak_points=["Citation grounding"],
            next_actions=["Review cited chunks"],
        ),
    )

    by_type = {signal["type"]: signal for signal in signals}
    assert by_type["confusion_detected"]["value"] is True
    assert by_type["needs_review"]["value"] is True
    assert by_type["evidence_used"]["value"] is True
    assert by_type["chapter_supervision_used"]["value"] is True


def test_session_tutor_graph_state_accepts_required_ids() -> None:
    state = SessionTutorGraphState(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        content="Explain grounded answers.",
        node_trace=[],
        learning_signals=[],
    )

    assert state["content"] == "Explain grounded answers."
    assert state["node_trace"] == []
```

- [ ] **Step 2: Run failing test**

```powershell
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_session_tutor_graph_state.py -q
```

Expected: fail because `session_tutor_graph` does not exist.

- [ ] **Step 3: Add state module**

Create `apps/api/app/domain/session_tutor_graph/__init__.py`:

```python
"""LangGraph-backed Session Tutor domain."""
```

Create `apps/api/app/domain/session_tutor_graph/state.py`:

```python
import uuid
from typing import NotRequired, TypedDict

from app.domain.agent_runtime.state import LearningSignal
from app.domain.chapter_mentor.schemas import ChapterMentorCitationResponse


class ChapterSupervision(TypedDict):
    summary: str
    weak_points: list[str]
    next_actions: list[str]


class RetrievedEvidence(TypedDict):
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    text: str
    score: float


class SessionTutorGraphState(TypedDict):
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    session_id: uuid.UUID
    content: str
    study_space_id: NotRequired[uuid.UUID]
    chapter_id: NotRequired[uuid.UUID]
    user_message_id: NotRequired[uuid.UUID]
    assistant_message_id: NotRequired[uuid.UUID]
    retrieved_chunks: NotRequired[list[RetrievedEvidence]]
    source_filenames: NotRequired[dict[uuid.UUID, str]]
    answer: NotRequired[str]
    citations: NotRequired[list[ChapterMentorCitationResponse]]
    chapter_supervision: NotRequired[ChapterSupervision | None]
    learning_signals: list[LearningSignal]
    node_trace: list[str]
    error_message: NotRequired[str]


def _has_confusion(content: str) -> bool:
    markers = ("confused", "confusing", "unclear", "stuck", "hard", "difficult", "不懂", "困惑", "卡住")
    lowered = content.lower()
    return any(marker in lowered for marker in markers)


def build_learning_signals(
    content: str,
    citation_count: int,
    chapter_supervision: ChapterSupervision | None,
) -> list[LearningSignal]:
    confusion_detected = _has_confusion(content)
    weak_points = chapter_supervision["weak_points"] if chapter_supervision else []
    return [
        {
            "type": "confusion_detected",
            "value": confusion_detected,
            "rationale": "Learner question includes confusion markers." if confusion_detected else "No explicit confusion marker was detected.",
        },
        {
            "type": "needs_review",
            "value": confusion_detected or bool(weak_points),
            "rationale": "Review is useful when the learner is confused or chapter weak points exist.",
        },
        {
            "type": "evidence_used",
            "value": citation_count > 0,
            "rationale": f"Assistant answer included {citation_count} citations.",
        },
        {
            "type": "chapter_supervision_used",
            "value": chapter_supervision is not None,
            "rationale": "Chapter Mentor state was loaded." if chapter_supervision else "No Chapter Mentor state was available.",
        },
    ]
```

- [ ] **Step 4: Verify task**

```powershell
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_session_tutor_graph_state.py -q
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m ruff check app/domain/session_tutor_graph/state.py tests/test_session_tutor_graph_state.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/session_tutor_graph apps/api/tests/test_session_tutor_graph_state.py
git commit -m "feat: add session tutor graph state"
```

---

### Task 3: Implement Graph Nodes and Runner

**Files:**

- Create: `apps/api/app/domain/session_tutor_graph/nodes.py`
- Create: `apps/api/app/domain/session_tutor_graph/graph.py`
- Create: `apps/api/app/domain/session_tutor_graph/service.py`
- Modify: `apps/api/app/domain/sessions/service.py`
- Test: `apps/api/tests/test_session_tutor_graph_service.py`

- [ ] **Step 1: Add failing graph service tests**

Create `apps/api/tests/test_session_tutor_graph_service.py`:

```python
import uuid
from types import SimpleNamespace

import pytest

from app.db.models import AgentRun, ChapterMentorState, Message, MessageRole
from app.domain.chapter_mentor.schemas import ChapterMentorCitationResponse, ChapterMentorResponse
from app.domain.rag.retrieval import RetrievedChunk
from app.domain.session_tutor_graph.service import run_session_tutor_graph


class FakeEmbeddingProvider:
    async def embed(self, _text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeAnswerProvider:
    async def answer(self, question: str, chunks: list, source_filenames: dict) -> ChapterMentorResponse:
        return ChapterMentorResponse(
            answer=f"Grounded answer for: {question}",
            citations=[
                ChapterMentorCitationResponse(
                    source_id=chunks[0].source_id,
                    chunk_id=chunks[0].chunk_id,
                    source_filename=source_filenames[chunks[0].source_id],
                    chunk_index=chunks[0].chunk_index,
                    text=chunks[0].text,
                    score=chunks[0].score,
                )
            ],
        )


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
            chunk_id=chunk_id,
            source_id=source_id,
            chunk_index=0,
            text="Evidence text",
            score=0.91,
            citation={"source_filename": "notes.md", "chunk_index": 0},
        )
    ]

    class FakeSession:
        async def scalar(self, _statement):
            if not hasattr(self, "scalar_calls"):
                self.scalar_calls = 0
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return tutor_session
            if self.scalar_calls == 2:
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

    async def fake_retrieve_chunks(**_kwargs):
        return retrieved

    async def fake_load_source_filenames(**_kwargs):
        return {source_id: "notes.md"}

    monkeypatch.setattr("app.domain.session_tutor_graph.nodes.retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr("app.domain.session_tutor_graph.nodes.load_source_filenames", fake_load_source_filenames)

    response = await run_session_tutor_graph(
        session=FakeSession(),
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        content="I am confused about citations.",
        embedding_provider=FakeEmbeddingProvider(),
        answer_provider=FakeAnswerProvider(),
    )

    messages = [obj for obj in added if isinstance(obj, Message)]
    runs = [obj for obj in added if isinstance(obj, AgentRun)]
    assert response.content == "Grounded answer for: I am confused about citations."
    assert len(messages) == 2
    assert messages[0].role == MessageRole.user
    assert messages[1].role == MessageRole.assistant
    assert len(runs) == 1
    assert runs[0].output_payload["node_trace"][-1] == "record_agent_run"
    assert runs[0].output_payload["chapter_supervision_used"] is True
    assert any(signal["type"] == "confusion_detected" for signal in runs[0].output_payload["learning_signals"])
```

- [ ] **Step 2: Run failing test**

```powershell
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_session_tutor_graph_service.py -q
```

Expected: fail because graph runner does not exist.

- [ ] **Step 3: Add graph nodes**

Create `apps/api/app/domain/session_tutor_graph/nodes.py` with node functions:

```python
from app.db.models import AgentRunStatus, MessageRole
from app.domain.chapter_mentor.service import load_source_filenames
from app.domain.chapter_mentor_state.service import get_chapter_mentor_state
from app.domain.rag.retrieval import retrieve_chunks
from app.domain.sessions.schemas import MessageCitationCreate, MessageCreate
from app.domain.sessions.service import (
    create_message,
    create_message_with_response,
    ensure_session_in_tenant,
    record_agent_run,
)
from app.domain.session_tutor_graph.state import (
    ChapterSupervision,
    RetrievedEvidence,
    SessionTutorGraphState,
    build_learning_signals,
)


def _trace(state: SessionTutorGraphState, node_name: str) -> None:
    state.setdefault("node_trace", []).append(node_name)


async def load_session_context(state: SessionTutorGraphState, *, db_session) -> SessionTutorGraphState:
    _trace(state, "load_session_context")
    tutor_session = await ensure_session_in_tenant(
        session=db_session,
        tenant_id=state["tenant_id"],
        session_id=state["session_id"],
    )
    state["study_space_id"] = tutor_session.study_space_id
    state["chapter_id"] = tutor_session.chapter_id
    return state


async def persist_user_message(state: SessionTutorGraphState, *, db_session) -> SessionTutorGraphState:
    _trace(state, "persist_user_message")
    message = await create_message(
        session=db_session,
        tenant_id=state["tenant_id"],
        session_id=state["session_id"],
        payload=MessageCreate(role=MessageRole.user, content=state["content"]),
    )
    state["user_message_id"] = message.id
    return state


async def load_chapter_supervision(state: SessionTutorGraphState, *, db_session) -> SessionTutorGraphState:
    _trace(state, "load_chapter_supervision")
    mentor_state = await get_chapter_mentor_state(
        session=db_session,
        tenant_id=state["tenant_id"],
        chapter_id=state["chapter_id"],
    )
    state["chapter_supervision"] = (
        ChapterSupervision(
            summary=mentor_state.summary,
            weak_points=mentor_state.weak_points or [],
            next_actions=mentor_state.next_actions or [],
        )
        if mentor_state
        else None
    )
    return state


async def retrieve_evidence(
    state: SessionTutorGraphState,
    *,
    db_session,
    embedding_provider,
) -> SessionTutorGraphState:
    _trace(state, "retrieve_evidence")
    chunks = await retrieve_chunks(
        session=db_session,
        tenant_id=state["tenant_id"],
        study_space_id=state["study_space_id"],
        query=state["content"],
        limit=5,
        embedding_provider=embedding_provider,
    )
    state["retrieved_chunks"] = [
        RetrievedEvidence(
            source_id=chunk.source_id,
            chunk_id=chunk.chunk_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            score=chunk.score,
        )
        for chunk in chunks
    ]
    source_filenames = await load_source_filenames(
        session=db_session,
        tenant_id=state["tenant_id"],
        study_space_id=state["study_space_id"],
        source_ids=[chunk.source_id for chunk in chunks],
    )
    state["source_filenames"] = source_filenames
    state["_raw_chunks"] = chunks  # type: ignore[typeddict-unknown-key]
    return state


async def generate_answer(state: SessionTutorGraphState, *, answer_provider) -> SessionTutorGraphState:
    _trace(state, "generate_answer")
    answer = await answer_provider.answer(
        question=state["content"],
        chunks=state.get("_raw_chunks", []),  # type: ignore[typeddict-item]
        source_filenames=state.get("source_filenames", {}),
    )
    state["answer"] = answer.answer
    state["citations"] = answer.citations
    return state


async def persist_assistant_message(state: SessionTutorGraphState, *, db_session) -> SessionTutorGraphState:
    _trace(state, "persist_assistant_message")
    response = await create_message_with_response(
        session=db_session,
        tenant_id=state["tenant_id"],
        session_id=state["session_id"],
        payload=MessageCreate(
            role=MessageRole.assistant,
            content=state["answer"],
            citations=[
                MessageCitationCreate(
                    source_id=citation.source_id,
                    source_chunk_id=citation.chunk_id,
                    quote=citation.text,
                    citation={
                        "source_filename": citation.source_filename,
                        "chunk_index": citation.chunk_index,
                    },
                )
                for citation in state.get("citations", [])
            ],
        ),
    )
    state["assistant_message_id"] = response.id
    state["_assistant_response"] = response  # type: ignore[typeddict-unknown-key]
    return state


async def extract_learning_signals(state: SessionTutorGraphState) -> SessionTutorGraphState:
    _trace(state, "extract_learning_signals")
    state["learning_signals"] = build_learning_signals(
        content=state["content"],
        citation_count=len(state.get("citations", [])),
        chapter_supervision=state.get("chapter_supervision"),
    )
    return state


async def record_graph_agent_run(state: SessionTutorGraphState, *, db_session) -> SessionTutorGraphState:
    _trace(state, "record_agent_run")
    await record_agent_run(
        session=db_session,
        tenant_id=state["tenant_id"],
        session_id=state["session_id"],
        message_id=state.get("assistant_message_id"),
        input_payload={
            "content": state["content"],
            "user_message_id": str(state.get("user_message_id")),
            "chapter_supervision_used": state.get("chapter_supervision") is not None,
        },
        output_payload={
            "assistant_message_id": str(state.get("assistant_message_id")),
            "citation_count": len(state.get("citations", [])),
            "node_trace": state["node_trace"],
            "learning_signals": state["learning_signals"],
            "chapter_supervision_used": state.get("chapter_supervision") is not None,
        },
        model="langgraph:deterministic",
        status=AgentRunStatus.completed,
    )
    return state
```

- [ ] **Step 4: Add graph builder and runner**

Create `apps/api/app/domain/session_tutor_graph/graph.py`:

```python
from langgraph.graph import END, StateGraph

from app.domain.session_tutor_graph import nodes
from app.domain.session_tutor_graph.state import SessionTutorGraphState


def build_session_tutor_graph(db_session, embedding_provider, answer_provider):
    graph = StateGraph(SessionTutorGraphState)
    graph.add_node(
        "load_session_context",
        lambda state: nodes.load_session_context(state, db_session=db_session),
    )
    graph.add_node(
        "persist_user_message",
        lambda state: nodes.persist_user_message(state, db_session=db_session),
    )
    graph.add_node(
        "load_chapter_supervision",
        lambda state: nodes.load_chapter_supervision(state, db_session=db_session),
    )
    graph.add_node(
        "retrieve_evidence",
        lambda state: nodes.retrieve_evidence(
            state,
            db_session=db_session,
            embedding_provider=embedding_provider,
        ),
    )
    graph.add_node(
        "generate_answer",
        lambda state: nodes.generate_answer(state, answer_provider=answer_provider),
    )
    graph.add_node(
        "persist_assistant_message",
        lambda state: nodes.persist_assistant_message(state, db_session=db_session),
    )
    graph.add_node("extract_learning_signals", nodes.extract_learning_signals)
    graph.add_node(
        "record_agent_run",
        lambda state: nodes.record_graph_agent_run(state, db_session=db_session),
    )

    graph.set_entry_point("load_session_context")
    graph.add_edge("load_session_context", "persist_user_message")
    graph.add_edge("persist_user_message", "load_chapter_supervision")
    graph.add_edge("load_chapter_supervision", "retrieve_evidence")
    graph.add_edge("retrieve_evidence", "generate_answer")
    graph.add_edge("generate_answer", "persist_assistant_message")
    graph.add_edge("persist_assistant_message", "extract_learning_signals")
    graph.add_edge("extract_learning_signals", "record_agent_run")
    graph.add_edge("record_agent_run", END)
    return graph.compile()
```

Create `apps/api/app/domain/session_tutor_graph/service.py`:

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chapter_mentor.providers import AnswerProvider
from app.domain.rag.embeddings import EmbeddingProvider
from app.domain.sessions.schemas import MessageResponse
from app.domain.session_tutor_graph.graph import build_session_tutor_graph
from app.domain.session_tutor_graph.state import SessionTutorGraphState


async def run_session_tutor_graph(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    embedding_provider: EmbeddingProvider,
    answer_provider: AnswerProvider,
) -> MessageResponse:
    graph = build_session_tutor_graph(
        db_session=session,
        embedding_provider=embedding_provider,
        answer_provider=answer_provider,
    )
    initial_state = SessionTutorGraphState(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        content=content,
        node_trace=[],
        learning_signals=[],
    )
    final_state = await graph.ainvoke(
        initial_state,
        config={
            "configurable": {
                "thread_id": f"session:{session_id}",
            }
        },
    )
    return final_state["_assistant_response"]
```

This closure-based graph builder avoids relying on version-specific config injection behavior for node dependencies. Keep graph node functions independently testable by passing dependencies as keyword-only arguments.

- [ ] **Step 5: Verify graph service**

```powershell
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_session_tutor_graph_state.py tests/test_session_tutor_graph_service.py -q
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m ruff check app/domain/session_tutor_graph tests/test_session_tutor_graph_state.py tests/test_session_tutor_graph_service.py
```

Expected: graph tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/domain/session_tutor_graph apps/api/tests/test_session_tutor_graph_state.py apps/api/tests/test_session_tutor_graph_service.py
git commit -m "feat: add session tutor langgraph runner"
```

---

### Task 4: Route Existing Session Tutor Service Through the Graph

**Files:**

- Modify: `apps/api/app/domain/sessions/service.py`
- Modify: `apps/api/app/api/routes_sessions.py` if `user_id` must be threaded into the service boundary.
- Modify: `apps/api/tests/test_session_routes.py`
- Modify: `apps/api/tests/test_session_service.py`

- [ ] **Step 1: Add failing route/service compatibility tests**

In `apps/api/tests/test_session_routes.py`, update `test_create_session_message_uses_answer_service` to assert `user_id` is passed:

```python
assert captured["user_id"] == uuid.UUID("00000000-0000-0000-0000-000000000002")
```

Add a service-level delegation test to `apps/api/tests/test_session_service.py`:

```python
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

    monkeypatch.setattr("app.domain.session_tutor_graph.service.run_session_tutor_graph", fake_run_session_tutor_graph)

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
```

Update imports in `test_session_service.py`:

```python
from app.domain.sessions.service import (
    answer_session_message,
    build_message_response,
    create_message,
    create_session_for_chapter,
    record_agent_run,
)
```

- [ ] **Step 2: Run failing tests**

```powershell
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_session_routes.py tests/test_session_service.py -q
```

Expected: fail because `answer_session_message()` does not accept `user_id` and route does not pass it.

- [ ] **Step 3: Update service boundary**

Change `answer_session_message()` signature and import the graph runner inside the function to avoid a circular import with graph nodes that reuse session persistence helpers:

```python
async def answer_session_message(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    embedding_provider: EmbeddingProvider,
    answer_provider: AnswerProvider,
) -> MessageResponse:
    from app.domain.session_tutor_graph.service import run_session_tutor_graph

    return await run_session_tutor_graph(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        content=content,
        embedding_provider=embedding_provider,
        answer_provider=answer_provider,
    )
```

Keep the previous inline implementation in git history only; do not leave a duplicate dead path unless graph enable/disable fallback is implemented in the same task.

- [ ] **Step 4: Update route**

In `apps/api/app/api/routes_sessions.py`, pass authorized user ID:

```python
return await answer_session_message(
    session=session,
    tenant_id=context.tenant_id,
    user_id=context.user_id,
    session_id=session_id,
    content=payload.content,
    embedding_provider=DeterministicEmbeddingProvider(settings.rag_embedding_dimension),
    answer_provider=create_answer_provider(settings),
)
```

- [ ] **Step 5: Verify compatibility**

```powershell
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_session_routes.py tests/test_session_service.py tests/test_session_tutor_graph_service.py -q
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m ruff check app/api/routes_sessions.py app/domain/sessions/service.py app/domain/session_tutor_graph tests/test_session_routes.py tests/test_session_service.py tests/test_session_tutor_graph_service.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/api/routes_sessions.py apps/api/app/domain/sessions/service.py apps/api/tests/test_session_routes.py apps/api/tests/test_session_service.py
git commit -m "feat: route session tutor through langgraph"
```

---

### Task 5: Failure Recording and Documentation

**Files:**

- Modify: `apps/api/app/domain/session_tutor_graph/service.py`
- Modify: `apps/api/tests/test_session_tutor_graph_service.py`
- Modify: `apps/api/README.md`
- Modify: `README.md`

- [ ] **Step 1: Add failing failure-recording test**

Append to `apps/api/tests/test_session_tutor_graph_service.py`:

```python
class FailingAnswerProvider:
    async def answer(self, question: str, chunks: list, source_filenames: dict) -> ChapterMentorResponse:
        raise RuntimeError("provider unavailable")


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

        async def refresh(self, obj) -> None:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def fake_retrieve_chunks(**_kwargs):
        return []

    async def fake_load_source_filenames(**_kwargs):
        return {}

    monkeypatch.setattr("app.domain.session_tutor_graph.nodes.retrieve_chunks", fake_retrieve_chunks)
    monkeypatch.setattr("app.domain.session_tutor_graph.nodes.load_source_filenames", fake_load_source_filenames)

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

    runs = [obj for obj in added if isinstance(obj, AgentRun)]
    assert len(runs) == 1
    assert runs[0].status.value == "failed"
    assert runs[0].error_message == "provider unavailable"
```

- [ ] **Step 2: Run failing test**

```powershell
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_session_tutor_graph_service.py -q
```

Expected: fail because failed run recording is not implemented.

- [ ] **Step 3: Implement failure recording**

In `apps/api/app/domain/session_tutor_graph/service.py`, wrap graph invocation:

```python
from app.db.models import AgentRunStatus
from app.domain.sessions.service import record_agent_run


async def run_session_tutor_graph(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    embedding_provider: EmbeddingProvider,
    answer_provider: AnswerProvider,
) -> MessageResponse:
    graph = build_session_tutor_graph(
        db_session=session,
        embedding_provider=embedding_provider,
        answer_provider=answer_provider,
    )
    initial_state = SessionTutorGraphState(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        content=content,
        node_trace=[],
        learning_signals=[],
    )
    try:
        final_state = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": f"session:{session_id}"}},
        )
    except Exception as exc:
        user_message_id = initial_state.get("user_message_id")
        if user_message_id is not None:
            await record_agent_run(
                session=session,
                tenant_id=tenant_id,
                session_id=session_id,
                input_payload={
                    "content": content,
                    "user_message_id": str(user_message_id),
                    "node_trace": initial_state.get("node_trace", []),
                },
                output_payload={},
                model="langgraph:deterministic",
                status=AgentRunStatus.failed,
                error_message=str(exc),
            )
        raise
    return final_state["_assistant_response"]
```

If LangGraph returns a copied state and `initial_state` does not receive node mutations, move the failure-recording try/except into a small imperative runner that invokes nodes sequentially for this phase, or ensure state mutation is preserved by using the final partial state returned by the graph runtime. Keep the public function name unchanged.

- [ ] **Step 4: Update docs**

In `apps/api/README.md`, add a `Session Tutor LangGraph` subsection near the existing session tutor section:

```markdown
## Session Tutor LangGraph

The session tutor message endpoint is backed by a LangGraph workflow. The route
contract remains unchanged: clients post a learner message and receive an
assistant `MessageResponse` with citations. Internally the graph loads session
context, stores the user message, reads optional Chapter Mentor state, retrieves
RAG evidence, generates a grounded answer, stores the assistant message, emits
learning signals, and records an `agent_runs` row.

The graph is the L3 execution agent in the three-layer design. It does not
mutate learning routes or planner actions. L1/L2 supervision is represented
through Chapter Mentor context and `learning_signals` in `agent_runs.output_payload`.
```

In root `README.md`, add one bullet under architecture notes:

```markdown
- Session Tutor uses a LangGraph-backed L3 workflow while preserving the existing message API.
```

- [ ] **Step 5: Verify task**

```powershell
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest tests/test_session_tutor_graph_service.py tests/test_session_routes.py tests/test_session_service.py -q
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m ruff check app/domain/session_tutor_graph app/domain/sessions/service.py app/api/routes_sessions.py tests/test_session_tutor_graph_service.py tests/test_session_routes.py tests/test_session_service.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/domain/session_tutor_graph/service.py apps/api/tests/test_session_tutor_graph_service.py apps/api/README.md README.md
git commit -m "feat: record session tutor graph failures"
```

---

### Task 6: Full Verification

**Files:**

- No code changes expected.

- [ ] **Step 1: Run API verification**

```powershell
cd F:\AIproject\study_agent\apps\api
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m pytest -q
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m ruff check .
F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe -m alembic history
```

Expected:

- All non-guarded API tests pass.
- Ruff reports `All checks passed!`.
- Alembic head remains `0008_planner_actions`; no migration is added in this phase.

- [ ] **Step 2: Run web regression verification**

```powershell
cd F:\AIproject\study_agent\apps\web
npm run test
npm run typecheck
npm run build
```

Expected:

- Web tests pass.
- Typecheck exits 0. The known Volar route-block plugin warning may appear.
- Build exits 0.

- [ ] **Step 3: Run repository checks**

```powershell
cd F:\AIproject\study_agent
docker compose -f infra/docker-compose.yml config
git diff --check
git status --short
```

Expected:

- Docker Compose config exits 0. The known local Docker config permission warning may appear.
- `git diff --check` has no whitespace errors.
- `git status --short` shows only intentional files before final commit, and clean after final commit.

- [ ] **Step 4: Final commit if needed**

If verification fixes were needed:

```powershell
git add apps/api
git commit -m "test: verify session tutor langgraph"
```

---

## Self-Review Checklist

- [ ] No new API endpoint is required.
- [ ] Existing session tutor route response shape is unchanged.
- [ ] LangGraph is introduced only behind the Session Tutor service boundary.
- [ ] Chapter Mentor state is read as supervision context but not mutated.
- [ ] Space Planner and planner actions are not mutated.
- [ ] No migration is added.
- [ ] Tests cover success, absent/present supervision, and failure recording.
- [ ] Full API and web verification commands are listed.

## Execution Recommendation

Use `superpowers:subagent-driven-development`.

Recommended subagent split:

1. Runtime config and dependencies.
2. Graph state and signal extraction.
3. Graph nodes and runner.
4. Service delegation and route compatibility.
5. Failure recording and docs.

Keep each worker on the files listed for its task. Do not run multiple workers that modify `sessions.service.py` at the same time.
