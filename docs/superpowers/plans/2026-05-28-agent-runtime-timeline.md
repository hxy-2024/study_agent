# Agent Runtime Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tenant-safe runtime timeline that makes the L1 Space Planner, L2 Chapter Mentor, and L3 Session Tutor runs visible in the product.

**Architecture:** Reuse existing `agent_runs` rows as the source of truth. Add read-only query services and API routes scoped by `CurrentUserContext`, then render compact runtime panels on the study space and chapter pages. `agent_runs` does not have a `chapter_id` column, so chapter scope is derived from `sessions.chapter_id` for session-backed runs and from `input_payload.chapter_id` or `output_payload.chapter_id` for planner or mentor runs.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, Nuxt 4, Vue 3, Vitest, pytest, ruff.

---

## Scope

Implement:

- `agent_runtime` response schemas and read service.
- Read-only endpoints:
  - `GET /api/v1/study-spaces/{study_space_id}/agent-runs`
  - `GET /api/v1/chapters/{chapter_id}/agent-runs`
  - `GET /api/v1/sessions/{session_id}/agent-runs`
- Study space runtime panel for L1/L2/L3 activity.
- Chapter runtime panel for L2/L3 traces.
- README notes and full verification.

Do not implement:

- New migrations.
- New agent execution behavior.
- SSE/WebSocket/token streaming.
- Production auth replacement.

## Files

Create:

- `apps/api/app/domain/agent_runtime/schemas.py`
- `apps/api/app/domain/agent_runtime/service.py`
- `apps/api/app/api/routes_agent_runtime.py`
- `apps/api/tests/test_agent_runtime_routes.py`
- `apps/web/tests/agent-runtime-timeline.spec.ts`

Modify:

- `apps/api/app/api/router.py`
- `apps/web/pages/spaces/[id]/index.vue`
- `apps/web/pages/chapters/[id]/index.vue`
- `apps/api/README.md`

---

### Task 1: Agent Runtime Read Model

**Files:**

- Create: `apps/api/app/domain/agent_runtime/schemas.py`
- Create: `apps/api/app/domain/agent_runtime/service.py`
- Test: `apps/api/tests/test_agent_runtime_routes.py`

- [ ] Add failing tests for graph metadata extraction, malformed learning signals, run summaries, payload-derived `chapter_id`, and `_build_timeline_item`.
- [ ] Implement `AgentRunGraphMetadata`, `AgentRunTimelineItem`, and `AgentRunTimelineResponse`.
- [ ] Implement `_extract_graph_metadata`, `_extract_learning_signals`, `_summarize_agent_run`, `_chapter_id_from_payloads`, `_bounded_limit`, and `_build_timeline_item`.
- [ ] Implement list functions for study-space, chapter, and session scopes. Validate parent scope first and fail with `ValueError` when not found for tenant.
- [ ] Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline\apps\api
.\.venv\Scripts\python.exe -m pytest tests/test_agent_runtime_routes.py -q
.\.venv\Scripts\python.exe -m ruff check app/domain/agent_runtime tests/test_agent_runtime_routes.py
```

- [ ] Commit:

```powershell
git add apps/api/app/domain/agent_runtime/schemas.py apps/api/app/domain/agent_runtime/service.py apps/api/tests/test_agent_runtime_routes.py
git commit -m "feat: add agent runtime timeline read model"
```

### Task 2: Runtime API Routes

**Files:**

- Create: `apps/api/app/api/routes_agent_runtime.py`
- Modify: `apps/api/app/api/router.py`
- Modify: `apps/api/tests/test_agent_runtime_routes.py`

- [ ] Add route tests for study-space success, chapter 404 mapping, and session success.
- [ ] Implement `routes_agent_runtime.py` with three `GET` endpoints returning `AgentRunTimelineResponse`.
- [ ] Register `routes_agent_runtime.router` in `apps/api/app/api/router.py`.
- [ ] Run focused pytest and ruff.
- [ ] Commit with `feat: expose agent runtime timeline routes`.

### Task 3: Study Space Runtime Panel

**Files:**

- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Create/modify: `apps/web/tests/agent-runtime-timeline.spec.ts`

- [ ] Add Vitest coverage that mocks `/study-spaces/{id}/agent-runs?limit=8`.
- [ ] Add `AgentRunTimelineItem` frontend type, loader, normalizer, and tier label helper.
- [ ] Render an `Agent runtime` panel with L1/L2/L3 label, status, summary, node trace, and signal kinds.
- [ ] Use the existing fresh teal visual language: white runtime rows, 8px radius, subtle teal border, restrained shadow.
- [ ] Run focused web tests and typecheck.
- [ ] Commit with `feat: show study space agent runtime timeline`.

### Task 4: Chapter Runtime Panel

**Files:**

- Modify: `apps/web/pages/chapters/[id]/index.vue`
- Modify: `apps/web/tests/agent-runtime-timeline.spec.ts`

- [ ] Add Vitest coverage that mocks `/chapters/{id}/agent-runs?limit=8`.
- [ ] Add chapter runtime loader and render a `Chapter runtime` panel near mentor state.
- [ ] Show L2 Mentor and L3 Tutor traces with status, summary, and node trace.
- [ ] Run focused web tests and typecheck.
- [ ] Commit with `feat: show chapter agent runtime timeline`.

### Task 5: Docs and Full Verification

**Files:**

- Modify: `apps/api/README.md`

- [ ] Document the three runtime endpoints and their tenant scope.
- [ ] Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline\apps\api
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m alembic history

cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline\apps\web
npm run test
npm run typecheck
npm run build

cd F:\AIproject\study_agent\.worktrees\codex-agent-runtime-timeline
docker compose -f infra/docker-compose.yml config
git diff --check
git status --short
```

- [ ] Commit with `docs: document agent runtime timeline`.

## Execution Notes

- Use one subagent per task.
- Review each subagent result before dispatching the next task.
- Do not create a PR until the user asks.
