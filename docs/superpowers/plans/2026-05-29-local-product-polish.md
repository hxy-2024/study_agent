# Local Product Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local personal learning product easier to run and more useful day to day.

**Architecture:** Implement four ordered slices. Each slice keeps existing domain boundaries and adds only the minimum API/UI/scripts needed for a local-first workflow.

**Tech Stack:** PowerShell, Docker Compose, FastAPI, SQLAlchemy 2 async, Nuxt 4, Vue 3, Vitest, pytest.

---

### Task 1: Local One-Command Startup

**Files:**
- Create: `scripts/dev-up.ps1`
- Create: `scripts/dev-check.ps1`
- Modify: `README.md`

- [ ] Add PowerShell script that verifies Docker, starts Postgres/Redis/MinIO, runs Alembic, and prints API/Web commands.
- [ ] Add health-check script that calls API health and Docker Compose config.
- [ ] Document usage.
- [ ] Verify scripts with syntax checks and dry-run-safe commands.

### Task 2: Personal Learning Dashboard

**Files:**
- Create or modify API dashboard domain/routes.
- Modify: `apps/web/pages/index.vue`
- Add focused API and web tests.

- [ ] Add dashboard summary endpoint for local current user.
- [ ] Include study spaces, pending planner actions, supervision refresh count, recent agent runs, and due/current chapters where available.
- [ ] Render a scannable dashboard as the first screen.
- [ ] Verify API and web tests.

### Task 3: Source Import Improvements

**Files:**
- Modify source/upload APIs and space page.
- Add tests.

- [ ] Add paste-text source creation for `.md`/text content without manual file upload.
- [ ] Add source rename/delete or archive if model supports it without migration; otherwise add minimal migration.
- [ ] Add re-run ingestion affordance for ready/failed text sources.
- [ ] Verify source library tests.

### Task 4: Chapter Notes and Highlights

**Files:**
- Add notes/highlights domain if schema change is needed.
- Modify chapter page.
- Add tests.

- [ ] Add chapter note save/load.
- [ ] Add lightweight evidence highlight markers tied to source chunks.
- [ ] Surface notes in chapter study page.
- [ ] Verify API and web tests.

### Commit Strategy

- `docs: plan local product polish`
- `feat: add local dev startup scripts`
- `feat: add personal learning dashboard`
- `feat: improve local source import`
- `feat: add chapter notes`
