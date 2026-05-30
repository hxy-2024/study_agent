# GitHub Primer UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Nuxt frontend into a cohesive GitHub/Primer-inspired local AI learning workspace.

**Architecture:** Keep the existing Vue pages and API calls, but replace the visual structure with shared Primer-like tokens, row-based layouts, compact controls, and floating overlays only where they communicate temporary context. Preserve all existing core workflows and route targets.

**Tech Stack:** Nuxt 4, Vue 3, Pinia, Vitest, scoped Vue CSS plus `apps/web/assets/css/main.css`.

---

## Files

- Modify: `apps/web/assets/css/main.css` for shared tokens, shell, buttons, inputs, overlays, dashboard primitives, and motion.
- Modify: `apps/web/app.vue` for the Primer-like topbar, drawer, settings modal, and runtime modal.
- Modify: `apps/web/pages/index.vue` for the GitHub dashboard layout.
- Modify: `apps/web/pages/spaces/new.vue` for the two-column create workflow and floating modals.
- Modify: `apps/web/pages/chapters/[id]/index.vue` for the one-screen learning workspace and floating session panel.
- Modify: `apps/web/pages/quizzes/[id].vue` for the row-based quiz experience.
- Modify tests in `apps/web/tests/*.spec.ts` only where visible copy or removed UI hooks intentionally change.

## Task 1: Global Shell And Primer Tokens

**Files:**
- Modify: `apps/web/assets/css/main.css`
- Modify: `apps/web/app.vue`
- Test: `apps/web/tests/app-shell.spec.ts`

- [ ] Replace current teal decorative background with Primer-like `#f6f8fa`, white surfaces, grey borders, blue links, green primary buttons, and red destructive states.
- [ ] Keep topbar on every page with hamburger, product mark, product name, compact nav context, and avatar.
- [ ] Convert drawer/settings/runtime overlays to floating bordered surfaces with 10-14px radius and real shadow.
- [ ] Preserve `runtime-status-button`, drawer open/close behavior, Settings behavior, and Home navigation to `/`.
- [ ] Run: `cd apps/web; npm run test -- app-shell.spec.ts`

## Task 2: Home Dashboard

**Files:**
- Modify: `apps/web/pages/index.vue`
- Modify: `apps/web/assets/css/main.css`
- Test: `apps/web/tests/dashboard.spec.ts`

- [ ] Rebuild home as three columns: left study-space list, middle recommendation/activity feed, right calendar and today agenda.
- [ ] Replace space cards with row list and border dividers.
- [ ] Keep search and New button at the top of the left column.
- [ ] Keep Continue study routing through `getContinueChapterId`.
- [ ] Keep delete-on-hover red trash behavior and archive/restore API behavior.
- [ ] Keep Main Agent recommendation flow, but render it as activity/feed content or a floating panel rather than a nested card.
- [ ] Run: `cd apps/web; npm run test -- dashboard.spec.ts`

## Task 3: Create Learning Space

**Files:**
- Modify: `apps/web/pages/spaces/new.vue`
- Modify: `apps/web/assets/css/main.css`
- Test: `apps/web/tests/create-space.spec.ts`

- [ ] Rebuild the create page as a compact two-column workspace.
- [ ] Keep left workflow order: space name, learning goal, model, material upload/paste, embedding model, Run ingestion.
- [ ] Keep right sticky route outline with editable route text, AI Render action, chapter list, and Generate chapter details button.
- [ ] Convert chunks and chapter details to centered floating modals with shadows and clear close/back actions.
- [ ] Preserve `data-testid` hooks for back, RAG, chunk modal, chapter modal, and confirm.
- [ ] Run: `cd apps/web; npm run test -- create-space.spec.ts`

## Task 4: Chapter Study Workspace

**Files:**
- Modify: `apps/web/pages/chapters/[id]/index.vue`
- Modify: `apps/web/assets/css/main.css`
- Test: `apps/web/tests/chapter-study.spec.ts`

- [ ] Keep the chapter rail with all route chapters and smooth collapse.
- [ ] Make the main chat workspace fill the available viewport; only the message thread scrolls on desktop.
- [ ] Render the right session/notes/progress area as a floating panel with border, radius, and shadow.
- [ ] Keep session create/select/rename/delete, note create/delete, quiz generation, complete chapter, and mentor message APIs.
- [ ] Keep send-to-red-square interrupt behavior.
- [ ] Remove default frontend surfaces for MCP and web-search toggles.
- [ ] Preserve markdown rendering in chat messages.
- [ ] Run: `cd apps/web; npm run test -- chapter-study.spec.ts`

## Task 5: Quiz Page

**Files:**
- Modify: `apps/web/pages/quizzes/[id].vue`
- Modify: `apps/web/assets/css/main.css`
- Test: `apps/web/tests/quiz-page.spec.ts`

- [ ] Rebuild quiz page with compact top row, bordered question sections, row-based options, and sticky submit area only if it does not create card stacking.
- [ ] Keep wrong selected option soft red and correct option stronger green.
- [ ] Keep markdown marker stripping.
- [ ] Preserve submit lockout after result.
- [ ] Run: `cd apps/web; npm run test -- quiz-page.spec.ts`

## Task 6: Verification

**Files:**
- Test-only execution.

- [ ] Run targeted tests: `cd apps/web; npm run test -- app-shell.spec.ts dashboard.spec.ts create-space.spec.ts chapter-study.spec.ts quiz-page.spec.ts`
- [ ] Run full web tests: `cd apps/web; npm run test`
- [ ] Run typecheck: `cd apps/web; npm run typecheck`
- [ ] Run build if tests pass: `cd apps/web; npm run build`
- [ ] Record the known Vue/Volar plugin warning if it still appears during typecheck.
