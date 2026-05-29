# Supervision Freshness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show when L3 Session Tutor signals are newer than L2 Chapter Mentor assessment, so L1/L2/L3 become a visible supervision loop.

**Architecture:** Add computed read models without schema changes. Chapter Mentor state responses expose latest tutor signal time and stale supervision status. Space Planner evidence carries the same chapter-level stale flag so the space dashboard can monitor it.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Pydantic v2, Nuxt 4, Vue 3, Vitest, pytest.

---

### Task 1: Backend Chapter Freshness

**Files:**
- Modify: `apps/api/app/domain/chapter_mentor_state/schemas.py`
- Modify: `apps/api/app/domain/chapter_mentor_state/service.py`
- Modify: `apps/api/app/api/routes_chapter_mentor_state.py`
- Test: `apps/api/tests/test_chapter_mentor_state_service.py`

- [ ] **Step 1: Write failing tests**

Add tests that verify a mentor state is stale when the latest completed session tutor run is newer than `updated_at`, fresh when older, and still readable when no mentor state exists.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_chapter_mentor_state_service.py -q`

Expected: fail because freshness fields and helper functions do not exist.

- [ ] **Step 3: Implement computed fields**

Add response fields:

```python
latest_session_tutor_run_at: datetime | None = None
needs_supervision_refresh: bool = False
```

Add service helpers that query latest completed L3 run for a chapter and compare timestamps against the mentor state.

- [ ] **Step 4: Re-run focused tests**

Run: `python -m pytest tests/test_chapter_mentor_state_service.py -q`

Expected: pass.

### Task 2: Space Planner Monitoring

**Files:**
- Modify: `apps/api/app/domain/space_planner/service.py`
- Test: `apps/api/tests/test_space_planner_service.py`

- [ ] **Step 1: Write failing tests**

Add tests showing planner evidence includes `needs_supervision_refresh` and that stale chapters are surfaced in risk/review builders.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_space_planner_service.py -q`

Expected: fail until evidence builder understands freshness.

- [ ] **Step 3: Implement planner evidence fields**

Extend evidence rows with:

```python
"latest_session_tutor_run_at": "...",
"mentor_state_updated_at": "...",
"needs_supervision_refresh": True
```

- [ ] **Step 4: Re-run focused tests**

Run: `python -m pytest tests/test_space_planner_service.py -q`

Expected: pass.

### Task 3: Frontend Supervision Callouts

**Files:**
- Modify: `apps/web/pages/chapters/[id]/index.vue`
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Test: `apps/web/tests/chapter-mentor-state.spec.ts`
- Test: `apps/web/tests/space-planner-panel.spec.ts`

- [ ] **Step 1: Write failing component tests**

Add tests for chapter callout and space planner stale supervision count.

- [ ] **Step 2: Run focused tests**

Run: `npm run test -- chapter-mentor-state.spec.ts space-planner-panel.spec.ts`

Expected: fail until UI renders new fields.

- [ ] **Step 3: Implement UI**

Render a small teal callout near mentor assessment and a compact count in Space Planner.

- [ ] **Step 4: Re-run focused tests**

Run: `npm run test -- chapter-mentor-state.spec.ts space-planner-panel.spec.ts`

Expected: pass.

### Task 4: Docs and Verification

**Files:**
- Modify: `apps/api/README.md`

- [ ] **Step 1: Document behavior**

Add a short note that supervision freshness is computed from completed L3 tutor runs and L2 mentor state timestamps.

- [ ] **Step 2: Run verification**

Run API focused/full tests, web focused/full tests, typecheck, build, ruff, and compose config.

- [ ] **Step 3: Commit**

Commit in small slices with messages:

```bash
git commit -m "docs: plan supervision freshness"
git commit -m "feat: expose supervision freshness"
git commit -m "feat: show supervision freshness"
git commit -m "docs: document supervision freshness"
```
