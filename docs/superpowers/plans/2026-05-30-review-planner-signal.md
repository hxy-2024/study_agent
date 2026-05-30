# Review Planner Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic `review_planner` candidates and feed them into Main Agent dashboard recommendations.

**Architecture:** Create a focused review planner domain module that computes structured candidates from chapters and mastery records. Extend dashboard recommendation ranking to consume those candidates, while keeping existing API contracts and frontend structure stable.

**Tech Stack:** FastAPI, SQLAlchemy models, Pydantic, Pytest, Nuxt/Vitest.

---

## File Structure

- Create `apps/api/app/domain/review_planner/__init__.py`
  - Package marker.
- Create `apps/api/app/domain/review_planner/schemas.py`
  - `ReviewCandidate` Pydantic schema.
- Create `apps/api/app/domain/review_planner/service.py`
  - Deterministic review candidate generation.
- Modify `apps/api/app/domain/dashboard/recommendations.py`
  - Accept `review_candidates` and prioritize them.
- Modify `apps/api/app/domain/dashboard/service.py`
  - Compute review candidates and pass them to recommendation builder.
- Test `apps/api/tests/test_review_planner.py`
  - Direct unit tests for candidate generation.
- Modify `apps/api/tests/test_dashboard_recommendations.py`
  - Ranking tests for review candidate use.
- Modify `apps/api/tests/test_dashboard_service.py`
  - Service integration and source signal count.
- Modify `apps/web/tests/dashboard.spec.ts`
  - Ensure extra source metadata does not break Main Agent rendering.

---

## Tasks

### Task 1: Review Planner Service

- [ ] Write failing tests for low mastery, stale mastery, and completed chapter without mastery.
- [ ] Add `ReviewCandidate` schema.
- [ ] Implement `build_review_candidates`.
- [ ] Run `uv run pytest tests/test_review_planner.py -q`.

### Task 2: Main Agent Signal Integration

- [ ] Write failing tests that review intent and balanced intent prefer review candidates.
- [ ] Extend `build_main_agent_recommendation` with `review_candidates`.
- [ ] Include `review_candidates` count in `source_signals`.
- [ ] Run dashboard recommendation tests.

### Task 3: Dashboard Service Wiring

- [ ] Write failing service test showing review candidates are passed into the recommendation.
- [ ] Compute candidates in `get_dashboard_summary` and `get_main_agent_recommendation`.
- [ ] Keep recommendation persistence unchanged.
- [ ] Run dashboard service and route tests.

### Task 4: Minimal Web Compatibility

- [ ] Add/adjust one dashboard test fixture with `source_signals.review_candidates`.
- [ ] Keep existing Main Agent UI structure unchanged.
- [ ] Run `npm run test -- dashboard.spec.ts`.

### Task 5: Verification

- [ ] Run `uv run pytest -q`.
- [ ] Run `uv run ruff check app tests`.
- [ ] Run `npm run test`.
- [ ] Run `npm run typecheck`.

