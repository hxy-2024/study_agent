# Agent Runtime Drilldown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users open a runtime timeline row and inspect the run details that explain what each agent did.

**Architecture:** Extend the existing read-only timeline response with safe operational fields from `agent_runs`, then add inline detail panels on the study space and chapter pages. The detail panel is local UI state only; it does not add mutations, migrations, or new routes.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, Nuxt 4, Vue 3, Vitest, pytest, ruff.

---

## Scope

Implement:

- Additional timeline fields: `completed_at`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `total_tokens`.
- Frontend drilldown state on study space and chapter runtime panels.
- Runtime row buttons with accessible expanded state.
- Detail content: runtime metadata, node trace, learning signals, error, timing, and token metrics.
- Tests and docs.

Do not implement:

- Raw prompt or raw payload display.
- New database columns.
- New API routes.
- Live streaming.

## Files

Modify:

- `apps/api/app/domain/agent_runtime/schemas.py`
- `apps/api/app/domain/agent_runtime/service.py`
- `apps/api/tests/test_agent_runtime_routes.py`
- `apps/web/pages/spaces/[id]/index.vue`
- `apps/web/pages/chapters/[id]/index.vue`
- `apps/web/tests/agent-runtime-timeline.spec.ts`
- `apps/api/README.md`

---

### Task 1: Backend Timeline Detail Fields

**Files:**

- Modify: `apps/api/app/domain/agent_runtime/schemas.py`
- Modify: `apps/api/app/domain/agent_runtime/service.py`
- Modify: `apps/api/tests/test_agent_runtime_routes.py`

- [ ] Add failing assertions in `test_build_timeline_item_uses_session_chapter_id_over_payload_chapter_id` for `completed_at`, `latency_ms`, `prompt_tokens`, `completion_tokens`, and `total_tokens`.
- [ ] Add those fields to `AgentRunTimelineItem`.
- [ ] Populate those fields in `_build_timeline_item` from the `AgentRun` row.
- [ ] Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline\apps\api
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m pytest tests/test_agent_runtime_routes.py -q
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m ruff check app/domain/agent_runtime tests/test_agent_runtime_routes.py
```

- [ ] Commit:

```powershell
git add apps/api/app/domain/agent_runtime/schemas.py apps/api/app/domain/agent_runtime/service.py apps/api/tests/test_agent_runtime_routes.py
git commit -m "feat: add agent runtime detail fields"
```

### Task 2: Study Space Runtime Drilldown

**Files:**

- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Modify: `apps/web/tests/agent-runtime-timeline.spec.ts`

- [ ] Extend the frontend `AgentRunTimelineItem` type with `graph_name`, `state_schema_version`, `completed_at`, `latency_ms`, `prompt_tokens`, `completion_tokens`, and `total_tokens`.
- [ ] Add `selectedAgentRunId` state, `selectedAgentRun` computed value, `toggleAgentRun(run)` helper, `formatRuntimeMetric(value, suffix)` helper, and `formatRuntimeDate(value)` helper.
- [ ] Turn each study space runtime row into a button-like expandable item using a real `<button type="button">` for the row header. Use `aria-expanded`.
- [ ] Render a detail panel for the selected row with:
  - `Thread`, `Graph`, `Checkpoint`, `Schema`, `Created`, `Completed`, `Latency`, `Tokens`.
  - Numbered node trace.
  - Learning signal chips.
  - Error message when present.
- [ ] Keep the visual style fresh teal, compact, and readable. Use 8px radius, white detail surface, subtle border, and no nested decorative cards.
- [ ] Update `agent-runtime-timeline.spec.ts` to click a study space runtime row and assert `thread-runtime-1`, `memory`, `load_session_context`, and `Latency` are visible.
- [ ] Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline\apps\web
npm run test -- agent-runtime-timeline.spec.ts
npm run typecheck
```

- [ ] Commit:

```powershell
git add apps/web/pages/spaces/[id]/index.vue apps/web/tests/agent-runtime-timeline.spec.ts
git commit -m "feat: add study space runtime drilldown"
```

### Task 3: Chapter Runtime Drilldown

**Files:**

- Modify: `apps/web/pages/chapters/[id]/index.vue`
- Modify: `apps/web/tests/agent-runtime-timeline.spec.ts`

- [ ] Apply the same drilldown type fields, state, helpers, row button, and detail panel to `apps/web/pages/chapters/[id]/index.vue`.
- [ ] Filter remains chapter-focused: show `chapter_mentor` and `session_tutor` rows only.
- [ ] Update `agent-runtime-timeline.spec.ts` to click a chapter runtime row and assert `thread-runtime-chapter`, `retrieve_evidence`, and `Tokens` are visible.
- [ ] Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline\apps\web
npm run test -- agent-runtime-timeline.spec.ts chapter-study.spec.ts chapter-mentor-state.spec.ts
npm run typecheck
```

- [ ] Commit:

```powershell
git add apps/web/pages/chapters/[id]/index.vue apps/web/tests/agent-runtime-timeline.spec.ts
git commit -m "feat: add chapter runtime drilldown"
```

### Task 4: Docs and Full Verification

**Files:**

- Modify: `apps/api/README.md`

- [ ] Add one paragraph to the Agent runtime timeline section explaining the drilldown fields.
- [ ] Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline\apps\api
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m pytest -q
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m ruff check .
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m alembic history

cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline\apps\web
npm run test
npm run typecheck
npm run build

cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline
docker compose -f infra/docker-compose.yml config
git diff --check
git status --short
```

- [ ] Commit:

```powershell
git add apps/api/README.md
git commit -m "docs: document runtime drilldown"
```

## Execution Notes

- Use one fresh subagent per task.
- Review every task result before dispatching the next task.
- Do not create a PR.
