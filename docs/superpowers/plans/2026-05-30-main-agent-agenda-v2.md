# Main Agent Agenda v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the homepage recommendation into a persisted Layer 1 Main Agent agenda decision with user-adjustable time and intent.

**Architecture:** Add a focused dashboard recommendation request/response contract, deterministic `main_agent_agenda_v2` strategy, and agent run persistence. Update the Nuxt dashboard Today card to request refreshed recommendations without changing low-level study artifacts.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Pytest, Nuxt/Vue, Vitest.

---

## File Structure

- Modify `apps/api/app/db/models.py`
  - Add `main_agent`, `review_planner`, and `quiz_mastery` to `AgentType`.
- Modify `apps/api/app/domain/dashboard/schemas.py`
  - Add recommendation request fields, strategy metadata, and agent run id.
- Modify `apps/api/app/domain/dashboard/recommendations.py`
  - Replace single chapter-first fallback with `main_agent_agenda_v2`.
- Modify `apps/api/app/domain/dashboard/service.py`
  - Gather richer signals and persist recommendation runs.
- Modify `apps/api/app/api/routes_dashboard.py`
  - Add `POST /dashboard/recommendation`.
- Modify `apps/api/tests/test_dashboard_recommendations.py`
  - Cover intent/time ranking.
- Modify `apps/api/tests/test_dashboard_service.py`
  - Cover run persistence and default dashboard integration.
- Modify `apps/api/tests/test_dashboard_routes.py`
  - Cover POST recommendation route.
- Modify `apps/web/pages/index.vue`
  - Add floating Main Agent conversation entry, chat state, recommendation refresh, and error state.
- Modify `apps/web/tests/dashboard.spec.ts`
  - Cover interaction behavior.

---

## Tasks

### Task 1: Backend Contract and Strategy

- [ ] Write failing tests for request schema and intent ranking.
- [ ] Add `DashboardRecommendationRequest`, metadata fields, and new agent enum values.
- [ ] Implement `main_agent_agenda_v2` ranking for balanced, new material, review, and quiz intents.
- [ ] Run focused backend tests.

### Task 2: Backend Persistence and Route

- [ ] Write failing tests for persisted `main_agent` agent run and POST route.
- [ ] Add service helper that builds and optionally records a recommendation run.
- [ ] Add `POST /api/v1/dashboard/recommendation`.
- [ ] Run dashboard route and service tests.

### Task 3: Dashboard Interaction UI

- [ ] Write failing Vitest tests for floating Main Agent conversation behavior.
- [ ] Add a floating Main Agent entry point and independent conversation window.
- [ ] Infer time and intent from user messages, then call POST refresh with loading and conversational error state.
- [ ] Run focused frontend tests.

### Task 4: Verification

- [ ] Run `python -m pytest tests/test_dashboard_recommendations.py tests/test_dashboard_service.py tests/test_dashboard_routes.py -q`.
- [ ] Run `python -m ruff check app tests`.
- [ ] Run `npm run test -- dashboard.spec.ts`.
- [ ] Run `npm run typecheck`.
