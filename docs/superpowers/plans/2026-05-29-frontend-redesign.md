# Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the main local product screens into a compact, fresh teal, GitHub-inspired study console.

**Architecture:** Keep existing Nuxt pages and API calls, but replace the page composition and shell layout. Use browser-local state for settings and calendar placeholders until backend persistence is added.

**Tech Stack:** Nuxt 4, Vue 3 Composition API, Vitest, scoped CSS, existing FastAPI endpoints.

---

### Task 1: Global Top Shell And Local Settings

**Files:**
- Modify: `apps/web/app.vue`
- Modify: `apps/web/assets/css/main.css`
- Modify: `apps/web/tests/app-shell.spec.ts`

- [ ] Replace the persistent sidebar with a top app bar containing hamburger, product icon, product name, runtime/search affordance, and avatar.
- [ ] Add a hamburger drawer containing Spaces, Library, Reviews, Progress, and Settings.
- [ ] Add a settings modal/drawer surface with base URL, API key, default model, and optional embedding model fields backed by local component state.
- [ ] Update app shell tests to assert the top bar, drawer destinations, avatar, and settings fields.
- [ ] Run `npm run test -- app-shell.spec.ts`.

### Task 2: GitHub-Style Home Dashboard

**Files:**
- Modify: `apps/web/pages/index.vue`
- Modify: `apps/web/tests/dashboard.spec.ts`

- [ ] Keep the existing `/dashboard` fetch fallback behavior.
- [ ] Sort spaces newest first using available array order, then expose a search filter by name or goal.
- [ ] Render the left space list with search and `New` button.
- [ ] Render a central continue panel for the selected/current space.
- [ ] Render a square calendar/events panel on the right.
- [ ] Update tests for empty state, newest-first list, search, New link, and calendar text.
- [ ] Run `npm run test -- dashboard.spec.ts app-shell.spec.ts`.

### Task 3: Create Study Space Workflow

**Files:**
- Modify: `apps/web/pages/spaces/new.vue`
- Modify: `apps/web/tests/create-space.spec.ts`

- [ ] Add top-left back arrow link.
- [ ] Recompose the form into setup, material/RAG, and generation steps.
- [ ] Add optional embedding model input.
- [ ] Hide chunk/embedded content behind a centered modal opened by a button.
- [ ] Add sticky right route outline with editable text and gradient `AI Render` label.
- [ ] Add `生成章节学习详情` action, loading text `正在生成中，请稍等`, and a larger chapter-detail modal with left chapter list, right detail pane, top-left back close, and bottom-right confirm.
- [ ] Preserve existing create/upload/ingestion/route-generation API behavior.
- [ ] Run `npm run test -- create-space.spec.ts`.

### Task 4: Chat-First Chapter Study Page

**Files:**
- Modify: `apps/web/pages/chapters/[id]/index.vue`
- Modify: `apps/web/tests/chapter-study.spec.ts`
- Modify: `apps/web/tests/chapter-mentor-state.spec.ts` if selectors move.

- [ ] Keep existing chapter, mentor, quiz, notes, and session APIs available.
- [ ] Recompose the page into collapsible chapter rail, AI chat canvas, floating session/progress/notes panel, and bottom composer.
- [ ] Render the default assistant introduction in the chat stream.
- [ ] Preserve markdown-like message formatting with readable pre-wrap text until a markdown renderer is introduced.
- [ ] Show checkpoint/fork controls under assistant messages.
- [ ] Add composer controls for attachment, model, thinking strength, and send `↑`.
- [ ] Run `npm run test -- chapter-study.spec.ts chapter-mentor-state.spec.ts`.

### Task 5: Verification And Polish

**Files:**
- Modify only files needed to fix issues found by verification.

- [ ] Run `npm run test`.
- [ ] Run `npm run typecheck`; record the known Vue language plugin warning if it still appears after successful generation.
- [ ] Run `npm run build`.
- [ ] Inspect responsive behavior for the three main screens and adjust CSS so primary controls fit without awkward overlap.

### Commit Strategy

- `docs: plan frontend redesign`
- `feat: redesign app shell and dashboard`
- `feat: redesign create study workflow`
- `feat: redesign chapter study chat`
