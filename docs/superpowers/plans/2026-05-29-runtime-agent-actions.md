# Runtime-driven Agent Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert recent L3 Session Tutor runtime signals into proposed planner review actions.

**Architecture:** Extend the existing `planner_actions` domain. Runtime-generated actions are normal `PlannerAction` rows with `action_type=review_chapter`, `status=proposed`, and `payload.source=runtime_signal`. The API is tenant/user scoped by `CurrentUserContext`; no new tables or automatic execution are added.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, existing planner action models, Nuxt 4, Vue 3, Vitest, pytest, ruff.

---

## Scope

Implement:

- `CreateRuntimeActionsRequest` schema.
- Runtime signal to planner action builder.
- `POST /api/v1/planner-actions/from-runtime-signals`.
- Study Space button for space-level runtime actions.
- Chapter button for chapter-scoped runtime actions.
- Tests and docs.

Do not implement:

- New migrations.
- Automatic route mutation.
- New planner action enum values.
- Background jobs.
- Raw prompt/payload display.

## Files

Modify:

- `apps/api/app/domain/planner_actions/schemas.py`
- `apps/api/app/domain/planner_actions/service.py`
- `apps/api/app/api/routes_planner_actions.py`
- `apps/api/tests/test_planner_actions.py`
- `apps/web/pages/spaces/[id]/index.vue`
- `apps/web/pages/chapters/[id]/index.vue`
- `apps/web/tests/planner-actions-panel.spec.ts`
- `apps/web/tests/chapter-review-callout.spec.ts`
- `apps/api/README.md`

---

### Task 1: Backend Runtime Action Builder

**Files:**

- Modify: `apps/api/app/domain/planner_actions/schemas.py`
- Modify: `apps/api/app/domain/planner_actions/service.py`
- Modify: `apps/api/tests/test_planner_actions.py`

- [ ] Add `CreateRuntimeActionsRequest` with `study_space_id: uuid.UUID` and `chapter_id: uuid.UUID | None = None`.
- [ ] Add helpers in service:
  - `_runtime_signal_types(output_payload) -> list[str]`
  - `_runtime_action_kind(signal_types) -> str | None`
  - `_runtime_action_title(kind, chapter_title) -> str`
  - `_runtime_action_rationale(signal_types) -> str`
- [ ] Add `create_actions_from_runtime_signals(session, tenant_id, user_id, study_space_id, chapter_id=None)`.
- [ ] Query completed `AgentRun` rows with `agent_type=session_tutor`, join `Session` and `Chapter`, and filter by study space / optional chapter.
- [ ] Generate at most 5 proposed `review_chapter` actions.
- [ ] Skip duplicate active actions where `payload.source == "runtime_signal"`, `payload.agent_run_id == run.id`, and `payload.action_kind == kind`.
- [ ] Action payload must include `source`, `action_kind`, `agent_run_id`, `session_id`, and `signal_types`.
- [ ] Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-runtime-agent-actions\apps\api
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m pytest tests/test_planner_actions.py -q
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m ruff check app/domain/planner_actions tests/test_planner_actions.py
```

- [ ] Commit:

```powershell
git add apps/api/app/domain/planner_actions/schemas.py apps/api/app/domain/planner_actions/service.py apps/api/tests/test_planner_actions.py
git commit -m "feat: build planner actions from runtime signals"
```

### Task 2: Runtime Actions API Route

**Files:**

- Modify: `apps/api/app/api/routes_planner_actions.py`
- Modify: `apps/api/tests/test_planner_actions.py`

- [ ] Add route:

```python
@router.post("/planner-actions/from-runtime-signals", response_model=PlannerActionListResponse, status_code=201)
```

- [ ] Use `CreateRuntimeActionsRequest`, `CurrentUserContext`, and `get_db_session`.
- [ ] Call `create_actions_from_runtime_signals`.
- [ ] Map `ValueError` through existing `map_planner_action_error`.
- [ ] Add route tests for success and 404 when study space is missing.
- [ ] Run focused pytest and ruff.
- [ ] Commit with `feat: expose runtime signal planner actions`.

### Task 3: Frontend Runtime Action Entry Points

**Files:**

- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Modify: `apps/web/pages/chapters/[id]/index.vue`
- Modify: `apps/web/tests/planner-actions-panel.spec.ts`
- Modify: `apps/web/tests/chapter-review-callout.spec.ts`

- [ ] Add Study Space state: `creatingRuntimeActions`, `runtimeActionsMessage`.
- [ ] Add `createRuntimeActions()` on Study Space page. It posts `{ study_space_id }` to `/planner-actions/from-runtime-signals`, then merges returned actions into `plannerActions`.
- [ ] Add button in planner actions panel: `Create runtime actions`.
- [ ] Add Chapter page state and `createRuntimeActions()` posting `{ study_space_id, chapter_id }`.
- [ ] Add button in chapter review callout: `Create runtime actions`.
- [ ] Empty response message: `No new runtime actions found.`
- [ ] Update Vitest mocks and assertions.
- [ ] Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-runtime-agent-actions\apps\web
npm run test -- planner-actions-panel.spec.ts chapter-review-callout.spec.ts
npm run typecheck
```

- [ ] Commit with `feat: add runtime action controls`.

### Task 4: Docs and Full Verification

**Files:**

- Modify: `apps/api/README.md`

- [ ] Document `POST /api/v1/planner-actions/from-runtime-signals`.
- [ ] Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-runtime-agent-actions\apps\api
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m pytest -q
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m ruff check .
F:\AIproject\study_agent\.worktrees\codex-session-tutor-langgraph\apps\api\.venv\Scripts\python.exe -m alembic history

cd F:\AIproject\study_agent\.worktrees\codex-runtime-agent-actions\apps\web
npm run test
npm run typecheck
npm run build

cd F:\AIproject\study_agent\.worktrees\codex-runtime-agent-actions
docker compose -f infra/docker-compose.yml config
git diff --check
git status --short
```

- [ ] Commit with `docs: document runtime signal actions`.

## Execution Notes

- Use one subagent per task.
- Review each result before dispatching the next task.
- Do not create a PR until the user asks.
