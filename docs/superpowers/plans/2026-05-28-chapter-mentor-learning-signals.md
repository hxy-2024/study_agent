# Chapter Mentor Learning Signals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Chapter Mentor consume Session Tutor graph `learning_signals` so L3 tutor runs influence L2 chapter supervision state.

**Architecture:** Reuse existing `agent_runs` JSON payloads. Extend `chapter_mentor_state.service` with small signal extraction helpers and include signals in weak points, next actions, and evidence during deterministic state generation.

**Tech Stack:** FastAPI domain service, SQLAlchemy async, existing `AgentRun`, `Session`, `ChapterMentorState`, pytest, ruff.

---

## Scope

Implement:

- Signal extraction helper for `AgentRun.output_payload.learning_signals`.
- Query Session Tutor runs for sessions under the target chapter.
- Include signal-derived weak points, next actions, and evidence in generated Chapter Mentor state.
- Tests for helper behavior and generated state enrichment.

Do not implement:

- New tables or migrations.
- New routes.
- Frontend changes.
- Space Planner aggregation.

## Files

Modify:

- `apps/api/app/domain/chapter_mentor_state/service.py`
- `apps/api/tests/test_chapter_mentor_state_service.py`
- `apps/api/README.md`

---

### Task 1: Add Signal Extraction and State Enrichment

**Files:**

- Modify: `apps/api/app/domain/chapter_mentor_state/service.py`
- Modify: `apps/api/tests/test_chapter_mentor_state_service.py`

- [ ] **Step 1: Add failing helper tests**

Add to `apps/api/tests/test_chapter_mentor_state_service.py`:

```python
from app.domain.chapter_mentor_state.service import build_signal_insights


def test_build_signal_insights_converts_learning_signals_to_state_inputs() -> None:
    insights = build_signal_insights(
        [
            {
                "run_id": "run-1",
                "session_id": "session-1",
                "signals": [
                    {
                        "type": "confusion_detected",
                        "value": True,
                        "rationale": "Learner question includes confusion markers.",
                    },
                    {
                        "type": "needs_review",
                        "value": True,
                        "rationale": "Review is useful.",
                    },
                    {
                        "type": "evidence_used",
                        "value": False,
                        "rationale": "Assistant answer included 0 citations.",
                    },
                ],
            }
        ]
    )

    assert "Recent tutor sessions show learner confusion." in insights.weak_points
    assert "Tutor answers need stronger cited evidence." in insights.weak_points
    assert "Run a focused review based on recent tutor confusion signals." in insights.next_actions
    assert insights.evidence[0]["run_id"] == "run-1"
```

- [ ] **Step 2: Run failing test**

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api
.\.venv\Scripts\python.exe -m pytest tests/test_chapter_mentor_state_service.py -q
```

Expected: fail because `build_signal_insights` does not exist.

- [ ] **Step 3: Implement signal helper**

In `apps/api/app/domain/chapter_mentor_state/service.py`, add near the existing helper functions:

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SignalInsights:
    weak_points: list[str]
    next_actions: list[str]
    evidence: list[dict]


def build_signal_insights(signal_runs: list[dict]) -> SignalInsights:
    weak_points: list[str] = []
    next_actions: list[str] = []
    evidence: list[dict] = []

    for run in signal_runs:
        signals = run.get("signals", [])
        if not isinstance(signals, list):
            continue
        true_signal_types = {
            signal.get("type")
            for signal in signals
            if isinstance(signal, dict) and signal.get("value") is True
        }
        false_signal_types = {
            signal.get("type")
            for signal in signals
            if isinstance(signal, dict) and signal.get("value") is False
        }
        if "confusion_detected" in true_signal_types:
            weak_points.append("Recent tutor sessions show learner confusion.")
        if "needs_review" in true_signal_types:
            next_actions.append("Run a focused review based on recent tutor confusion signals.")
        if "evidence_used" in false_signal_types:
            weak_points.append("Tutor answers need stronger cited evidence.")
        if "chapter_supervision_used" in true_signal_types:
            evidence.append(
                {
                    "kind": "learning_signal",
                    "run_id": run.get("run_id"),
                    "session_id": run.get("session_id"),
                    "signal_types": sorted(true_signal_types),
                }
            )
        elif true_signal_types or false_signal_types:
            evidence.append(
                {
                    "kind": "learning_signal",
                    "run_id": run.get("run_id"),
                    "session_id": run.get("session_id"),
                    "signal_types": sorted(true_signal_types | false_signal_types),
                }
            )

    return SignalInsights(
        weak_points=list(dict.fromkeys(weak_points))[:3],
        next_actions=list(dict.fromkeys(next_actions))[:3],
        evidence=evidence[:5],
    )
```

- [ ] **Step 4: Query signal runs during generation**

Inside `generate_chapter_mentor_state()`, after messages are loaded, query completed Session Tutor runs:

```python
signal_run_rows = await session.scalars(
    select(AgentRun)
    .join(Session, AgentRun.session_id == Session.id)
    .where(
        AgentRun.tenant_id == tenant_id,
        AgentRun.agent_type == AgentType.session_tutor,
        AgentRun.status == AgentRunStatus.completed,
        Session.chapter_id == chapter_id,
    )
    .order_by(AgentRun.created_at.desc(), AgentRun.id)
)
signal_runs = [
    {
        "run_id": str(run.id),
        "session_id": str(run.session_id),
        "signals": (run.output_payload or {}).get("learning_signals", []),
    }
    for run in list(signal_run_rows)[:10]
]
signal_insights = build_signal_insights(signal_runs)
```

When writing state:

```python
state.weak_points = list(dict.fromkeys(_build_weak_points(messages) + signal_insights.weak_points))[:3]
state.next_actions = list(dict.fromkeys(_build_next_actions(messages) + signal_insights.next_actions))[:3]
state.evidence = (_build_evidence(messages) + signal_insights.evidence)[:8]
```

- [ ] **Step 5: Add generation test**

Add a test in `apps/api/tests/test_chapter_mentor_state_service.py` that monkeypatches or fakes session scalars so `generate_chapter_mentor_state()` receives:

- a chapter
- one message
- one completed `AgentRun` with `learning_signals`

Assert:

```python
assert any("learner confusion" in item.lower() for item in result.weak_points)
assert any("focused review" in item.lower() for item in result.next_actions)
assert any(item.get("kind") == "learning_signal" for item in result.evidence)
```

- [ ] **Step 6: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chapter_mentor_state_service.py tests/test_chapter_mentor_state_routes.py tests/test_session_tutor_graph_service.py -q
.\.venv\Scripts\python.exe -m ruff check app/domain/chapter_mentor_state tests/test_chapter_mentor_state_service.py tests/test_chapter_mentor_state_routes.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/app/domain/chapter_mentor_state/service.py apps/api/tests/test_chapter_mentor_state_service.py
git commit -m "feat: feed tutor signals into chapter mentor"
```

---

### Task 2: Documentation and Verification

**Files:**

- Modify: `apps/api/README.md`

- [ ] **Step 1: Update API docs**

In `apps/api/README.md`, update the Chapter Mentor or Session Tutor section:

```markdown
Chapter Mentor state generation also reads Session Tutor `learning_signals`
from completed graph-backed tutor runs. Those signals enrich weak points,
next actions, and evidence without changing the public API response shape.
```

- [ ] **Step 2: Run verification**

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m alembic history
```

Expected:

- API tests pass.
- Ruff passes.
- Alembic head remains `0008_planner_actions`.

- [ ] **Step 3: Commit docs if needed**

```powershell
git add apps/api/README.md
git commit -m "docs: document tutor signal feedback"
```
