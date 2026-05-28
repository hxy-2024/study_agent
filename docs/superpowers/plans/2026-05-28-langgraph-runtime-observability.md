# LangGraph Runtime Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize LangGraph runtime metadata and checkpoint boundaries for graph-backed Session Tutor runs.

**Architecture:** Extend `agent_runtime` with thread ID, metadata, and checkpointer helpers. Wire those helpers into `session_tutor_graph.service` so successful and failed `AgentRun` payloads carry consistent graph metadata. Keep API behavior unchanged and fail closed for unsupported production checkpoint setup.

**Tech Stack:** FastAPI domain modules, LangGraph, existing `AgentRun` persistence, pytest, ruff.

---

## Scope

Implement:

- Stable `thread_id` helper.
- Runtime metadata builder.
- Checkpointer factory boundary for `none`, `memory`, and reserved `postgres`.
- Session Tutor graph uses runtime metadata for success and failure runs.
- Tests for metadata, checkpoint config, success payload, and failure payload.

Do not implement:

- SSE streaming.
- Postgres checkpoint table setup.
- Background workers.
- New routes.
- Frontend changes.

## Files

Modify:

- `apps/api/app/domain/agent_runtime/config.py`
- `apps/api/app/domain/agent_runtime/state.py`
- `apps/api/app/domain/session_tutor_graph/graph.py`
- `apps/api/app/domain/session_tutor_graph/service.py`
- `apps/api/tests/test_agent_runtime_config.py`
- `apps/api/tests/test_session_tutor_graph_service.py`
- `apps/api/README.md`

Create:

- `apps/api/app/domain/agent_runtime/metadata.py`
- `apps/api/app/domain/agent_runtime/checkpoints.py`
- `apps/api/tests/test_agent_runtime_metadata.py`

---

### Task 1: Runtime Metadata Helpers

**Files:**

- Create: `apps/api/app/domain/agent_runtime/metadata.py`
- Test: `apps/api/tests/test_agent_runtime_metadata.py`

- [ ] **Step 1: Add failing metadata tests**

Create `apps/api/tests/test_agent_runtime_metadata.py`:

```python
import uuid

from app.domain.agent_runtime.metadata import (
    SESSION_TUTOR_GRAPH_NAME,
    STATE_SCHEMA_VERSION,
    build_graph_metadata,
    session_tutor_thread_id,
)


def test_session_tutor_thread_id_is_stable() -> None:
    session_id = uuid.UUID("00000000-0000-0000-0000-000000000123")

    assert session_tutor_thread_id(session_id) == "session:00000000-0000-0000-0000-000000000123"


def test_build_graph_metadata_uses_standard_contract() -> None:
    metadata = build_graph_metadata(
        graph_name=SESSION_TUTOR_GRAPH_NAME,
        thread_id="session:abc",
        checkpoint_backend="memory",
        node_trace=["load_session_context"],
    )

    assert metadata == {
        "graph_name": "session_tutor",
        "thread_id": "session:abc",
        "checkpoint_backend": "memory",
        "state_schema_version": STATE_SCHEMA_VERSION,
        "node_trace": ["load_session_context"],
    }
```

- [ ] **Step 2: Run failing test**

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api
.\.venv\Scripts\python.exe -m pytest tests/test_agent_runtime_metadata.py -q
```

Expected: fail because `agent_runtime.metadata` does not exist.

- [ ] **Step 3: Implement metadata helpers**

Create `apps/api/app/domain/agent_runtime/metadata.py`:

```python
import uuid
from typing import TypedDict

from app.domain.agent_runtime.config import CheckpointBackend


SESSION_TUTOR_GRAPH_NAME = "session_tutor"
STATE_SCHEMA_VERSION = 1


class GraphRunMetadata(TypedDict):
    graph_name: str
    thread_id: str
    checkpoint_backend: CheckpointBackend
    state_schema_version: int
    node_trace: list[str]


def session_tutor_thread_id(session_id: uuid.UUID | str) -> str:
    return f"session:{session_id}"


def build_graph_metadata(
    graph_name: str,
    thread_id: str,
    checkpoint_backend: CheckpointBackend,
    node_trace: list[str],
) -> GraphRunMetadata:
    return {
        "graph_name": graph_name,
        "thread_id": thread_id,
        "checkpoint_backend": checkpoint_backend,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "node_trace": list(node_trace),
    }
```

- [ ] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_runtime_metadata.py -q
.\.venv\Scripts\python.exe -m ruff check app/domain/agent_runtime tests/test_agent_runtime_metadata.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/agent_runtime/metadata.py apps/api/tests/test_agent_runtime_metadata.py
git commit -m "feat: add graph runtime metadata helpers"
```

---

### Task 2: Checkpointer Factory Boundary

**Files:**

- Create: `apps/api/app/domain/agent_runtime/checkpoints.py`
- Modify: `apps/api/tests/test_agent_runtime_config.py`

- [ ] **Step 1: Add failing checkpoint tests**

Append to `apps/api/tests/test_agent_runtime_config.py`:

```python
import pytest

from app.domain.agent_runtime.checkpoints import create_checkpointer
from app.domain.agent_runtime.config import GraphRuntimeConfig


def test_create_checkpointer_returns_none_for_none_backend() -> None:
    config = GraphRuntimeConfig(session_tutor_graph_enabled=True, checkpoint_backend="none")

    assert create_checkpointer(config) is None


def test_create_checkpointer_accepts_memory_backend() -> None:
    config = GraphRuntimeConfig(session_tutor_graph_enabled=True, checkpoint_backend="memory")

    assert create_checkpointer(config) is not None


def test_create_checkpointer_fails_closed_for_postgres_backend() -> None:
    config = GraphRuntimeConfig(session_tutor_graph_enabled=True, checkpoint_backend="postgres")

    with pytest.raises(ValueError, match="Postgres graph checkpointing is not configured"):
        create_checkpointer(config)
```

- [ ] **Step 2: Run failing tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_runtime_config.py -q
```

Expected: fail because `agent_runtime.checkpoints` does not exist.

- [ ] **Step 3: Implement checkpointer factory**

Create `apps/api/app/domain/agent_runtime/checkpoints.py`:

```python
from langgraph.checkpoint.memory import MemorySaver

from app.domain.agent_runtime.config import GraphRuntimeConfig


def create_checkpointer(config: GraphRuntimeConfig):
    if config.checkpoint_backend == "none":
        return None
    if config.checkpoint_backend == "memory":
        return MemorySaver()
    if config.checkpoint_backend == "postgres":
        raise ValueError("Postgres graph checkpointing is not configured")
    raise ValueError("Unsupported graph checkpoint backend")
```

- [ ] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_runtime_config.py -q
.\.venv\Scripts\python.exe -m ruff check app/domain/agent_runtime tests/test_agent_runtime_config.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/agent_runtime/checkpoints.py apps/api/tests/test_agent_runtime_config.py
git commit -m "feat: add graph checkpointer factory"
```

---

### Task 3: Wire Metadata Into Session Tutor Graph Runs

**Files:**

- Modify: `apps/api/app/domain/session_tutor_graph/graph.py`
- Modify: `apps/api/app/domain/session_tutor_graph/service.py`
- Modify: `apps/api/tests/test_session_tutor_graph_service.py`

- [ ] **Step 1: Add failing metadata assertions**

In `apps/api/tests/test_session_tutor_graph_service.py`, update success-path assertions:

```python
assert runs[0].output_payload["graph_name"] == "session_tutor"
assert runs[0].output_payload["thread_id"] == f"session:{session_id}"
assert runs[0].output_payload["checkpoint_backend"] == "memory"
assert runs[0].output_payload["state_schema_version"] == 1
```

Update failure-path assertions:

```python
assert runs[0].input_payload["graph_name"] == "session_tutor"
assert runs[0].input_payload["thread_id"] == f"session:{session_id}"
assert runs[0].input_payload["checkpoint_backend"] == "memory"
assert runs[0].input_payload["state_schema_version"] == 1
```

- [ ] **Step 2: Run failing graph service tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_session_tutor_graph_service.py -q
```

Expected: fail because graph metadata is not yet recorded.

- [ ] **Step 3: Update graph builder to accept checkpointer**

In `apps/api/app/domain/session_tutor_graph/graph.py`, change builder signature:

```python
def build_session_tutor_graph(db_session, embedding_provider, answer_provider, checkpointer=None):
    ...
    return graph.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: Update graph service**

In `apps/api/app/domain/session_tutor_graph/service.py`:

- Load settings and runtime config.
- Build `thread_id` with `session_tutor_thread_id(session_id)`.
- Build checkpointer with `create_checkpointer(config)`.
- Pass checkpointer into graph builder.
- Include graph metadata in success and failure payloads.

Expected imports:

```python
from app.core.config import get_settings
from app.domain.agent_runtime.checkpoints import create_checkpointer
from app.domain.agent_runtime.config import graph_runtime_config_from_settings
from app.domain.agent_runtime.metadata import (
    SESSION_TUTOR_GRAPH_NAME,
    build_graph_metadata,
    session_tutor_thread_id,
)
```

When recording success:

```python
metadata = build_graph_metadata(
    graph_name=SESSION_TUTOR_GRAPH_NAME,
    thread_id=thread_id,
    checkpoint_backend=runtime_config.checkpoint_backend,
    node_trace=state["node_trace"],
)
output_payload={**metadata, ...}
```

When recording failure:

```python
metadata = build_graph_metadata(
    graph_name=SESSION_TUTOR_GRAPH_NAME,
    thread_id=thread_id,
    checkpoint_backend=runtime_config.checkpoint_backend,
    node_trace=node_trace,
)
input_payload={**metadata, "content": content, "user_message_id": user_message_id}
```

- [ ] **Step 5: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_runtime_metadata.py tests/test_agent_runtime_config.py tests/test_session_tutor_graph_service.py -q
.\.venv\Scripts\python.exe -m ruff check app/domain/agent_runtime app/domain/session_tutor_graph tests/test_agent_runtime_metadata.py tests/test_agent_runtime_config.py tests/test_session_tutor_graph_service.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/domain/session_tutor_graph/graph.py apps/api/app/domain/session_tutor_graph/service.py apps/api/tests/test_session_tutor_graph_service.py
git commit -m "feat: record graph runtime metadata"
```

---

### Task 4: Documentation and Full Verification

**Files:**

- Modify: `apps/api/README.md`

- [ ] **Step 1: Update docs**

Add to `apps/api/README.md`:

```markdown
Graph-backed Session Tutor runs include standardized runtime metadata in
`agent_runs`: `graph_name`, `thread_id`, `checkpoint_backend`,
`state_schema_version`, and `node_trace`. The default checkpoint backend is
`memory`; `postgres` is reserved and fails closed until production checkpoint
storage is configured.
```

- [ ] **Step 2: Run full verification**

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m alembic history

cd F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\web
npm run test
npm run typecheck
npm run build

cd F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph
docker compose -f infra/docker-compose.yml config
git diff --check
git status --short
```

Expected:

- API tests pass.
- Ruff passes.
- Alembic head remains `0008_planner_actions`.
- Web tests/typecheck/build pass. The known Volar warning may appear.
- Docker Compose config exits 0. The known Docker config permission warning may appear.
- Worktree is clean after final commit.

- [ ] **Step 3: Commit docs**

```powershell
git add apps/api/README.md
git commit -m "docs: document graph runtime metadata"
```
