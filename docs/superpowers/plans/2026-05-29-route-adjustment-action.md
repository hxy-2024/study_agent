# Route Adjustment Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `route_adjustment` planner actions create draft learning routes for user review without mutating the active route.

**Architecture:** Reuse existing route/chapter tables. Add idempotent action execution metadata under `PlannerAction.payload.execution.route_draft_id`. Clone active route content into a new draft and apply a deterministic adjustment.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Pydantic v2, Nuxt 4, Vue 3, Vitest, pytest.

---

### Task 1: Backend Route Draft Execution

**Files:**
- Modify: `apps/api/app/domain/planner_actions/schemas.py`
- Modify: `apps/api/app/domain/planner_actions/service.py`
- Modify: `apps/api/app/api/routes_planner_actions.py`
- Test: `apps/api/tests/test_planner_actions_service.py`
- Test: `apps/api/tests/test_planner_actions_routes.py`

- [ ] Write failing tests for `insert_review` draft creation and idempotent reuse.
- [ ] Write failing route test for authorized `route-draft` execution.
- [ ] Implement `PlannerActionRouteDraftResponse`.
- [ ] Implement active route clone with deterministic `insert_review` and `extend_route`.
- [ ] Expose the route.
- [ ] Run focused planner action tests.

### Task 2: Frontend Route Draft Action

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Test: `apps/web/tests/planner-actions-panel.spec.ts`

- [ ] Write failing test for `Generate draft`.
- [ ] Add handler for route adjustment actions.
- [ ] Merge returned action and draft route into page state.
- [ ] Show route draft in the existing route panel so user can activate it.
- [ ] Run focused web test.

### Task 3: Docs and Verification

**Files:**
- Modify: `apps/api/README.md`

- [ ] Document the `route-draft` action endpoint.
- [ ] Run full API/Web verification.
- [ ] Commit in small slices.
