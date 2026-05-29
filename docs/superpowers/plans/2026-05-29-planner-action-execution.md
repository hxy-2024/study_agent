# Planner Action Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let accepted planner review actions start a focused mentor session and carry the learner into the chapter workflow.

**Architecture:** Add an idempotent backend execution service and endpoint. Reuse existing `sessions` storage and encode action execution metadata in `PlannerAction.payload` to avoid a migration. Add frontend buttons that call the endpoint and route to the selected chapter session.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Pydantic v2, Nuxt 4, Vue 3, Vitest, pytest.

---

### Task 1: Backend Execution Endpoint

**Files:**
- Modify: `apps/api/app/domain/planner_actions/schemas.py`
- Modify: `apps/api/app/domain/planner_actions/service.py`
- Modify: `apps/api/app/api/routes_planner_actions.py`
- Test: `apps/api/tests/test_planner_actions_service.py`
- Test: `apps/api/tests/test_planner_actions_routes.py`

- [ ] Write failing service tests for creating a review session and reusing an existing one.
- [ ] Write failing route test for `POST /planner-actions/{action_id}/start-review`.
- [ ] Implement `PlannerActionExecutionResponse`.
- [ ] Implement `start_review_for_planner_action`.
- [ ] Expose the route with tenant/user context.
- [ ] Run focused planner action tests.

### Task 2: Frontend Execution Flow

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Modify: `apps/web/pages/chapters/[id]/index.vue`
- Test: `apps/web/tests/planner-actions-panel.spec.ts`
- Test: `apps/web/tests/chapter-review-callout.spec.ts`

- [ ] Write failing tests for `Start review`.
- [ ] Add frontend response types and execution handler.
- [ ] Show the button for active review actions.
- [ ] Navigate to `/chapters/{chapter_id}?session_id={session_id}`.
- [ ] Make chapter mentor session loader prefer `route.query.session_id`.
- [ ] Run focused web tests.

### Task 3: Docs and Verification

**Files:**
- Modify: `apps/api/README.md`

- [ ] Document the start-review endpoint.
- [ ] Run API tests, ruff, web tests, typecheck, build, compose config, and diff check.
- [ ] Commit in small slices.
