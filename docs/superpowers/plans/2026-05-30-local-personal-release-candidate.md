# Local Personal Release Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current local personal study agent into a release-candidate product with a trustworthy learning loop, configurable AI behavior, data safety, and reliable local startup.

**Architecture:** Keep the product scoped to a local single-user workflow and do not introduce a login/user-entry system. Build on the existing three-layer agent model: L1 Main Agent decides the next learning move, L2 planners/mentor-state/review services produce structured signals, and L3 session tutor handles chapter-level RAG chat through the existing LangGraph runtime. Prefer deterministic read models and existing tables first; add storage only when user preferences or local backup state must persist.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Alembic where unavoidable, LangGraph only for multi-step agent execution, Nuxt/Vitest, Pytest, Ruff, local Docker services, `main.py` local launcher.

---

## Execution Rule

Do this as one large product task, but land it as small commits/checkpoints. The recommended worker split is:

- Worker A: Mentor citations and source jump.
- Worker B: AI/local settings and prompt/version audit.
- Worker C: Review queue, quiz retake, and Main Agent signal ranking.
- Worker D: Local runtime, backup/restore, demo seed, and docs.
- Main agent: integrate results, resolve conflicts, run full verification, and keep the product direction coherent.

Do not create a PR until the user asks.

---

## File Structure

### Backend

- Create `apps/api/app/domain/citations/__init__.py`
- Create `apps/api/app/domain/citations/schemas.py`
- Create `apps/api/app/domain/citations/service.py`
  - Expands saved message citations into source-aware, UI-ready citation cards.
- Modify `apps/api/app/domain/sessions/schemas.py`
  - Add expandable citation fields without breaking existing message responses.
- Modify `apps/api/app/domain/sessions/service.py`
  - Load citation source/chunk metadata when listing or creating mentor messages.
- Create `apps/api/app/domain/local_settings/__init__.py`
- Create `apps/api/app/domain/local_settings/schemas.py`
- Create `apps/api/app/domain/local_settings/service.py`
  - Stores local-only AI preferences in an ignored runtime file, with masked API key responses.
- Create `apps/api/app/api/routes_local_settings.py`
  - Exposes local AI settings and answer-style preferences.
- Modify `apps/api/app/api/router.py`
  - Register local settings routes.
- Modify `apps/api/app/domain/chapter_mentor/providers.py`
  - Use local settings overlay for provider/base URL/model/API key and answer style.
- Modify `apps/api/app/domain/session_tutor_graph/service.py`
  - Persist prompt version, answer style, web search mode, and provider metadata in agent runs.
- Create `apps/api/app/domain/review_queue/__init__.py`
- Create `apps/api/app/domain/review_queue/schemas.py`
- Create `apps/api/app/domain/review_queue/service.py`
  - Builds a unified queue from review candidates, quiz mastery, planner actions, and recent learning activity.
- Create `apps/api/app/domain/learning_signals/__init__.py`
- Create `apps/api/app/domain/learning_signals/schemas.py`
- Create `apps/api/app/domain/learning_signals/service.py`
  - Materializes L1/L2/L3 signals for audit, dedup, cooldown, and recommendation reuse.
- Create `apps/api/migrations/versions/0011_learning_signals_review_schedule.py`
  - Adds durable signal, review schedule, review event, and mastery event tables if current models cannot support them.
- Create `apps/api/app/api/routes_review_queue.py`
  - Provides the queue for dashboard/review views.
- Modify `apps/api/app/domain/dashboard/recommendations.py`
  - Consume the unified queue and user preferences in L1 Main Agent ranking.
- Modify `apps/api/app/domain/dashboard/service.py`
  - Pass local preferences, recent sessions, review queue, and quiz mastery into recommendation generation.
- Modify `apps/api/app/domain/quizzes/schemas.py`
- Modify `apps/api/app/domain/quizzes/service.py`
- Modify `apps/api/app/api/routes_quizzes.py`
  - Add retake support, wrong-answer review payloads, and mastery trend response fields.
- Create `apps/api/app/domain/local_backup/__init__.py`
- Create `apps/api/app/domain/local_backup/schemas.py`
- Create `apps/api/app/domain/local_backup/service.py`
  - Builds local backup manifests and export/restore commands.
- Create `apps/api/app/api/routes_local_backup.py`
  - Exposes backup status and latest manifest metadata; destructive restore remains CLI-only.
- Modify `main.py`
  - Add or harden `dev`, `check`, `reset-db`, `seed-demo`, `backup`, and `restore`.
- Modify `apps/api/app/domain/study_spaces/export.py`
  - Ensure exports include sources, route, notes, quizzes, quiz submissions, mentor sessions/messages/citations, planner actions, and agent runs.
- Create `apps/api/app/domain/study_spaces/import_restore.py`
  - Imports exported study-space archives with dry-run validation and ID remapping.
- Modify `apps/api/app/api/routes_study_spaces.py`
  - Add import/restore endpoint if a UI/API restore path is implemented.
- Modify `apps/api/app/api/routes_sources.py`
  - Add stable source jump/read endpoints such as source chunk detail and source download/read URL.
- Modify `apps/api/app/infrastructure/storage.py`
  - Add source object export/import or read URL helpers for backups and citation drill-through.

### Frontend

- Modify `apps/web/pages/index.vue`
  - Surface Main Agent agenda, review queue, quiz retake signals, local runtime status, and backup/export actions without redesigning the whole dashboard.
- Modify `apps/web/pages/chapters/[id]/index.vue`
  - Add expandable citation details and jump links to source/chunk context.
- Modify `apps/web/pages/spaces/[id]/index.vue`
  - Support source/chunk deep links and highlight the referenced chunk.
- Modify `apps/web/pages/quizzes/[id].vue`
  - Add retake, wrong-answer review, and mastery trend view.
- Create `apps/web/pages/settings.vue`
  - Local AI settings page for provider, base URL, model, API key, web search default, and answer style.
- Optionally create focused components under `apps/web/components/` only if a page exceeds practical maintainability:
  - `MentorCitationList.vue`
  - `ReviewQueuePanel.vue`
  - `LocalSettingsPanel.vue`
  - `RuntimeStatusPanel.vue`

### Tests

- Create `apps/api/tests/test_citation_expansion.py`
- Create `apps/api/tests/test_local_settings.py`
- Create `apps/api/tests/test_review_queue.py`
- Create `apps/api/tests/test_local_backup.py`
- Modify `apps/api/tests/test_session_service.py`
- Modify `apps/api/tests/test_session_routes.py`
- Modify `apps/api/tests/test_chapter_mentor_providers.py`
- Modify `apps/api/tests/test_session_tutor_graph_service.py`
- Modify `apps/api/tests/test_dashboard_recommendations.py`
- Modify `apps/api/tests/test_dashboard_service.py`
- Modify `apps/api/tests/test_quizzes.py`
- Modify `apps/api/tests/test_study_space_export.py`
- Modify `apps/web/tests/chapter-study.spec.ts`
- Modify `apps/web/tests/dashboard.spec.ts`
- Modify `apps/web/tests/quiz-page.spec.ts`
- Create `apps/web/tests/settings.spec.ts`
- Create `apps/web/tests/source-jump.spec.ts`

### Docs

- Modify `README.md`
- Modify `apps/api/README.md`
- Create or update `docs/local-personal-release.md`

---

## Task 0: Stabilize Current Signal Branch

**Purpose:** Preserve the already completed Review Planner + Quiz Mastery signal work before adding more moving parts.

- [ ] Run `git status --short --branch` in `F:\AIproject\study_agent\.worktrees\codex-review-planner-signal`.
- [ ] Confirm the current uncommitted changes are only Review Planner, Quiz Mastery, dashboard signal integration, and related tests/docs.
- [ ] Run API tests:
  - `cd apps/api`
  - `$env:PYTHONPATH = "$PWD"`
  - `F:\AIproject\study_agent\.worktrees\codex-local-stability-data-safety\apps\api\.venv\Scripts\python.exe -m pytest -q`
- [ ] Run API lint:
  - `F:\AIproject\study_agent\.worktrees\codex-local-stability-data-safety\apps\api\.venv\Scripts\python.exe -m ruff check app tests`
- [ ] Run web tests:
  - `cd apps/web`
  - `npm run test`
- [ ] Run web typecheck:
  - `npm run typecheck`
- [ ] If all verification still passes, keep this as the base for the larger product task.

---

## Task 1: Mentor Citation Expansion + Source Jump

**Purpose:** Make mentor answers trustworthy by letting the learner expand citations and jump back to the uploaded material chunk.

- [ ] Add `CitationDetail` and `CitationJumpTarget` schemas in `apps/api/app/domain/citations/schemas.py`.
- [ ] Implement `expand_message_citations(session, tenant_id, message_ids)` in `apps/api/app/domain/citations/service.py`.
- [ ] Join `MessageCitation -> SourceChunk -> Source`, returning:
  - `citation_id`
  - `message_id`
  - `source_id`
  - `source_filename`
  - `chunk_id`
  - `chunk_index`
  - `text`
  - `citation`
  - `jump_url`
  - `available`
- [ ] Return an unavailable citation object when the chunk or source no longer exists.
- [ ] Modify session message serialization so existing `/sessions/{id}/messages` responses include the expanded fields.
- [ ] Add stable backend jump payloads so the frontend does not have to infer source URLs:
  - `source_jump.space_id`
  - `source_jump.source_id`
  - `source_jump.chunk_id`
  - `source_jump.chunk_url`
  - `source_jump.source_url`
- [ ] Add `GET /sources/{source_id}/chunks/{chunk_id}` for one chunk lookup inside the authorized tenant.
- [ ] Add either `GET /sources/{source_id}/download` or `GET /sources/{source_id}/read-url` for local source drill-through.
- [ ] Add route/service tests covering normal citation, missing chunk, and cross-tenant denial.
- [ ] Update chapter mentor UI so citation cards are collapsed by default and expandable per citation.
- [ ] Add a citation link to `/spaces/{space_id}?source_id={source_id}&chunk_id={chunk_id}`.
- [ ] Update space page to read `source_id` and `chunk_id` query params, select the source, load chunks, and highlight the chunk.
- [ ] Add Vitest coverage for expanding a citation and source jump query behavior.

Verification:

- [ ] `python -m pytest tests/test_citation_expansion.py tests/test_session_service.py tests/test_session_routes.py -q`
- [ ] `python -m pytest tests/test_sources_routes.py -q`
- [ ] `npm run test -- chapter-study.spec.ts source-jump.spec.ts`

---

## Task 2: Local AI Settings + Prompt Audit

**Purpose:** Let a local user configure AI provider behavior from the app while keeping web search explicit and answer behavior inspectable.

- [ ] Add local settings storage under a gitignored runtime path such as `.local/settings.json`.
- [ ] Add `.local/` to `.gitignore` if it is not already ignored.
- [ ] Implement settings fields:
  - `llm_provider`
  - `llm_base_url`
  - `llm_model`
  - `llm_api_key`
  - `web_search_default_enabled`
  - `answer_style`: `concise`, `socratic`, `exam_review`, `code_tutor`
- [ ] Return masked API key values from the read API, never the raw key.
- [ ] Overlay local settings on environment settings inside provider creation.
- [ ] Keep deterministic provider as the no-key fallback.
- [ ] Include answer style instructions in the mentor prompt.
- [ ] Record `prompt_version`, `answer_style`, `llm_provider`, `llm_model`, and `web_search_enabled` in agent run metadata/output payload.
- [ ] Add settings page with clear local-only wording:
  - Provider
  - Base URL
  - Model
  - API key
  - Default web search toggle
  - Answer style segmented control
- [ ] Ensure the chapter mentor web search SVG toggle still sends per-message `web_search_enabled` and overrides the default.

Verification:

- [ ] `python -m pytest tests/test_local_settings.py tests/test_chapter_mentor_providers.py tests/test_session_tutor_graph_service.py -q`
- [ ] `npm run test -- settings.spec.ts chapter-study.spec.ts app-shell.spec.ts`

---

## Task 3: Unified Review Queue + Quiz Retake Loop

**Purpose:** Convert the current review/quiz signals into visible learning actions the user can follow and complete.

- [ ] Implement `ReviewQueueItem` with fields:
  - `id`
  - `kind`: `continue_chapter`, `review_chapter`, `retake_quiz`, `planner_action`
  - `study_space_id`
  - `chapter_id`
  - `quiz_id`
  - `title`
  - `reason`
  - `priority`
  - `estimated_minutes`
  - `action_url`
  - `source_signals`
- [ ] Build queue items from:
  - review planner candidates
  - quiz mastery signals
  - pending planner actions
  - incomplete route chapters
  - recent session/message activity
- [ ] Add `GET /review-queue`.
- [ ] Add `GET /study-spaces/{id}/review-queue`.
- [ ] Update Main Agent recommendation ranking to prefer the highest priority queue item while honoring available minutes and user intent.
- [ ] Add quiz retake endpoint or service method that creates a new quiz attempt from weak points without deleting prior submissions.
- [ ] Add wrong-answer review payload:
  - submitted answer
  - correct answer
  - explanation
  - linked source/citation when available
  - weak point label
- [ ] Update dashboard to show the queue as the source behind the Main Agent suggestion.
- [ ] Update quiz page with:
  - retake button
  - previous attempt summary
  - weak point trend
  - wrong-answer review after submission

Verification:

- [ ] `python -m pytest tests/test_review_queue.py tests/test_dashboard_recommendations.py tests/test_dashboard_service.py tests/test_quizzes.py -q`
- [ ] `npm run test -- dashboard.spec.ts quiz-page.spec.ts`

---

## Task 4: Durable Learning Signal Pipeline

**Purpose:** Move from purely read-time helper functions to auditable L1/L2/L3 signals that can be deduped, cooled down, dismissed, completed, and reused.

- [ ] Add a `learning_signals` model/table if existing `AgentRun.output_payload` is not enough.
- [ ] Use a schema with:
  - `id`
  - `tenant_id`
  - `user_id`
  - `study_space_id`
  - `chapter_id`
  - `quiz_id`
  - `agent_type`
  - `signal_type`
  - `priority`
  - `status`: `active`, `completed`, `dismissed`, `snoozed`
  - `dedupe_key`
  - `available_at`
  - `expires_at`
  - `payload`
  - `created_at`
  - `updated_at`
- [ ] Materialize review planner signals with dedupe keys such as `review:{chapter_id}:{reason}`.
- [ ] Materialize quiz mastery retake signals with dedupe keys such as `quiz-retake:{quiz_id}:{latest_submission_id}`.
- [ ] Materialize session tutor learning signals from completed L3 `AgentRun` output payload.
- [ ] Make dashboard `GET /dashboard` read-only: it may read the latest recommendation but must not create noisy agent runs.
- [ ] Keep explicit `POST /dashboard/recommendation` as the point that records an L1 Main Agent run.
- [ ] Add signal status endpoints:
  - complete
  - dismiss
  - snooze
- [ ] Update review queue to consume durable active signals first and fall back to computed signals only when no materialized signal exists.

Verification:

- [ ] `python -m pytest tests/test_learning_signals.py tests/test_review_queue.py tests/test_dashboard_service.py -q`
- [ ] `python -m pytest tests/test_dashboard_routes.py tests/test_agent_runtime_routes.py -q`

---

## Task 5: Main Agent Preference Signal Pipeline

**Purpose:** Make “今天先学什么” feel like a main-agent decision instead of a fixed dashboard rule.

- [ ] Extend recommendation request handling with:
  - available minutes
  - intent
  - energy level
  - optional rest window
  - user text prompt
- [ ] Parse common prompt hints locally:
  - “只学 10 分钟” -> available minutes 10
  - “复习” -> review intent
  - “测试/quiz” -> quiz intent
  - “太累/轻松” -> low energy
- [ ] Add local preference defaults from settings.
- [ ] Record each recommendation request as an L1 `AgentRun` with:
  - input payload
  - selected queue item
  - rejected alternatives
  - source signal counts
- [ ] Link the selected queue item back to its durable learning signal when one exists.
- [ ] Support dismiss/snooze/complete feedback from the recommendation card so the Main Agent stops repeating stale advice.
- [ ] Keep L1 deterministic for now. Do not migrate Main Agent to LangGraph until it performs multi-step planning with tool calls, confirmation, and resumable state.
- [ ] Update dashboard Main Agent conversation to show why the recommendation changed and which signals were used.

Verification:

- [ ] `python -m pytest tests/test_dashboard_recommendations.py tests/test_dashboard_service.py tests/test_agent_runtime_routes.py -q`
- [ ] `npm run test -- dashboard.spec.ts`

---

## Task 6: Local Data Safety

**Purpose:** Make local data recoverable before the user invests serious study time.

- [ ] Add `main.py backup`:
  - create timestamped backup folder under `.local/backups/`
  - dump Postgres using containerized `pg_dump` when Docker services are running
  - copy/export MinIO object data or document the fallback path
  - include `.env` only when the user passes an explicit flag such as `--include-env`
  - write `manifest.json` with app version, migration head, timestamp, and included artifacts
- [ ] Add `main.py restore <backup-path>`:
  - require confirmation unless `--yes`
  - stop API/web subprocesses if launched by `main.py`
  - restore Postgres dump
  - restore MinIO data when present
  - run migrations after restore
- [ ] Add `main.py seed-demo`:
  - create a demo study space with a small Markdown source
  - ingest it
  - generate route
  - create one mentor session/message and one quiz/submission if service calls allow it
- [ ] Add `main.py reset-db`:
  - clearly warn that local data will be removed
  - reset Docker Postgres volume only after confirmation
  - run migrations after reset
- [ ] Add local backup status panel or dashboard actions for:
  - Export current space
  - Create backup
  - Last backup manifest if available
- [ ] Extend study-space export to include:
  - mastery records and mastery history/events
  - quiz questions, submissions, results, weak points
  - mentor state
  - planner state/actions
  - agent runs
  - session messages and message citations
  - source object manifest
- [ ] Add study-space import/restore with dry-run validation:
  - schema version check
  - ID remapping
  - tenant/user rewrite for local current user
  - duplicate source handling
  - clear validation errors before writing
- [ ] Keep destructive full restore primarily in CLI; API import can restore a space archive without dropping the whole database.

Verification:

- [ ] `python main.py check`
- [ ] `python main.py backup --dry-run`
- [ ] `python main.py seed-demo --dry-run` if dry-run is implemented
- [ ] `python -m pytest tests/test_local_backup.py tests/test_study_space_export.py tests/test_study_space_import_restore.py -q`

---

## Task 7: Local Runtime Polish

**Purpose:** Make startup failures readable and make the first-run path reliable.

- [ ] Harden `main.py dev`:
  - check `uv`, `node`, `npm`, and Docker availability
  - check ports 8000 and 3000 before spawning
  - print the exact frontend and API URLs
  - print how to stop the process
- [ ] Harden `main.py check`:
  - Docker service status
  - DB connection
  - Alembic head/current
  - MinIO bucket status
  - API health
  - web dependency install status
  - LLM provider status
- [ ] Keep `python main.py dev --skip-install` and document correct subcommand argument placement.
- [ ] Add Windows helpers only if they are thin wrappers:
  - `scripts/dev.ps1`
  - `scripts/check.ps1`
- [ ] Update runtime status UI to use the same labels as `main.py check`.

Verification:

- [ ] `python main.py check`
- [ ] `python main.py dev --skip-install`
- [ ] Open `http://127.0.0.1:3000` and complete the happy path once.

---

## Task 8: Minimal Frontend Maintainability Pass

**Purpose:** Improve maintainability without fighting the user’s current frontend rewrite.

- [ ] Do not redesign the app shell.
- [ ] Extract components only where repeated state or tests become painful:
  - citation list
  - review queue panel
  - local settings form
  - runtime status panel
- [ ] Normalize button, empty, error, and destructive action behavior in the touched areas.
- [ ] Confirm mobile behavior for:
  - dashboard Main Agent panel
  - chapter mentor composer
  - session list scrolling
  - citation expansion
  - quiz retake summary
- [ ] Avoid moving unrelated CSS during this task unless necessary for the touched UI.

Verification:

- [ ] `npm run test`
- [ ] `npm run typecheck`
- [ ] `npm run build`
- [ ] Manual screenshot check on desktop/tablet/mobile if a dev server is available.

---

## Task 9: LangGraph Boundary Cleanup

**Purpose:** Keep LangGraph useful and bounded instead of letting it spread into deterministic read models too early.

- [ ] Make `session_tutor_graph_enabled` actually control the session tutor execution path.
- [ ] Merge or remove duplicate graph builders if `apps/api/app/domain/session_tutor_graph/graph.py` and `service.py` diverge.
- [ ] Keep `MemorySaver` as the default local checkpoint backend unless Postgres checkpointing is explicitly configured and tested.
- [ ] If Postgres checkpointing is enabled, add idempotency keys before nodes write DB rows.
- [ ] Record graph checkpoint backend and graph enabled/disabled status in runtime status and agent run metadata.
- [ ] Do not move L1 Main Agent to LangGraph in this task; document the later trigger conditions instead.

Verification:

- [ ] `python -m pytest tests/test_agent_runtime_config.py tests/test_session_tutor_graph_service.py tests/test_agent_runtime_routes.py -q`

---

## Task 10: Documentation and Release Checklist

**Purpose:** Make the local personal product usable without developer memory.

- [ ] Update README with a “5 minute local start” path:
  - prerequisites
  - Docker one-command start
  - Python `main.py` start
  - first-run demo seed
  - how to configure LLM
  - how to keep web search off unless explicitly enabled
  - backup/restore commands
- [ ] Add `docs/local-personal-release.md` with:
  - current product scope
  - what each agent layer does
  - when LangGraph is used
  - known local-only limitations
  - troubleshooting
- [ ] Document agent layers:
  - L1 Main Agent: chooses next study move from signals, user preference, time, and recent activity.
  - L2 Planner/Mentor State/Review Services: summarize route state, mastery, weak points, review candidates, and planner actions.
  - L3 Session Tutor: runs chapter-level RAG chat and web-search-optional answer generation through LangGraph.
- [ ] Add final verification section with exact commands and known acceptable warnings.

Verification:

- [ ] `python -m pytest -q`
- [ ] `python -m ruff check app tests`
- [ ] `npm run test`
- [ ] `npm run typecheck`
- [ ] `npm run build`
- [ ] `docker compose -f infra/docker-compose.yml config`

---

## LangGraph Boundary

Use LangGraph when the agent workflow has all three properties:

1. Multiple nodes with distinct responsibilities, such as retrieve evidence, optional web search, generate answer, extract learning signals.
2. Runtime state worth tracing or resuming.
3. Output that should be inspected later through agent runtime observability.

Current fit:

- Keep LangGraph for L3 Session Tutor.
- Do not move L1 Main Agent recommendation into LangGraph yet; it is currently a deterministic signal ranker plus lightweight conversation parser.
- Consider LangGraph for L1 later when it can propose a plan, ask for confirmation, execute actions, remember rejected choices, and resume a multi-step agenda.
- Consider LangGraph for L2 only if mentor-state/review-planner starts running multiple tools and generating persisted planner actions in one supervised flow.

---

## Final Acceptance Criteria

- The homepage answers “今天先学什么” using Main Agent signals, not a hardcoded rule.
- Mentor answers show expandable citations and can jump back to uploaded source chunks.
- Web search is explicit, default-off, and visibly separate from uploaded-material evidence.
- AI provider/model/style can be configured locally from the app.
- Review and quiz retake actions form a visible loop.
- Local data can be exported, backed up, restored, reset, and demo-seeded.
- `python main.py dev` and Docker startup both work for a local user.
- README explains the local workflow without needing prior chat context.
