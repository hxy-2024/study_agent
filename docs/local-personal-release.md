# Local Personal Release

## Scope

This release is a local personal study agent. It keeps the development auth
headers and avoids a user login surface. The product loop is:

1. Create a study space.
2. Upload local Markdown or text material.
3. Ingest sources and generate a route.
4. Study chapters with the L3 Session Tutor.
5. Use quizzes, mastery, planner actions, and review signals to decide what to do next.

## Runtime Profiles

| Mode | Command | DB | Source storage | Use |
| --- | --- | --- | --- | --- |
| local/dev | `python main.py local` | SQLite | `.local/storage` | Personal fast startup |
| docker-dev | `python main.py docker-dev` | Postgres | MinIO | Host debugging with real infrastructure |
| docker | `python main.py docker` | Postgres | MinIO | Migration and deployment checks |

`python main.py dev` is an alias for `python main.py local`. The local/dev
profile uses SQLite and filesystem source storage only for personal local
runtime. Docker-backed and deployed modes still use Postgres, pgvector, Redis,
and MinIO.

Migration note: local SQLite is not the production database and is not a
replacement for the Postgres migration path. Keep Alembic/Postgres as the
deployment schema source, and treat `.local/study_agent.db` as local runtime
state.

## Agent Layers

- L1 Main Agent: chooses the next dashboard action from user intent, available time, review queue, quiz mastery, planner actions, and recent progress. It is deterministic for now and records explicit recommendation requests as `AgentRun` rows.
- L2 planning agents and services: Space Planner, Chapter Mentor State, Review Planner, Quiz Mastery, and Review Queue produce structured signals that L1 can rank.
- L3 Session Tutor: answers chapter questions with RAG citations. LangGraph is used here because the workflow has multiple steps: load context, save the user message, retrieve evidence, optionally run web search, generate an answer, save citations, extract learning signals, and record the run.

`SESSION_TUTOR_GRAPH_ENABLED=false` switches L3 to a simpler deterministic RAG
path that still saves messages, citations, and agent runs. L1 should move to
LangGraph later only when it needs multi-step tool use, confirmation, and resumable
planning state.

## Data Safety

- Study space export payloads use schema version `1` and include the currently modeled learning state: sources/chunks, routes/chapters, sessions/messages/citations, quizzes/questions/submissions/results, mastery records, mentor states, planner states/actions, agent runs, and notes.
- `POST /study-spaces/import` defaults to `dry_run=true`. Dry runs validate the schema version and internal ID references, then return a count summary, tenant/user rewrite preview, and generated ID remap preview without writing rows.
- Full restore writes are intentionally blocked until table-by-table persistence is implemented. Calling the import endpoint with `dry_run=false` returns an explicit not-implemented response instead of reporting a successful restore.

Local whole-app backup is available from the launcher:

```powershell
python main.py backup --dry-run
python main.py backup
python main.py backup --include-env
```

Backups are written to `.local/backups/local-<timestamp>/` by default and include
`postgres.sql`, MinIO data, and `manifest.json`. `.env` is copied only when
`--include-env` is passed.

Restore is intentionally explicit because it replaces local data:

```powershell
python main.py restore .local\backups\local-YYYYMMDD-HHMMSS
python main.py restore .local\backups\local-YYYYMMDD-HHMMSS --yes
```

The dry run prints what would happen. `--yes` starts Postgres/MinIO, clears the
local public schema and MinIO data, restores the dump/files, and reruns migrations.

`python main.py reset-db --yes` removes local Docker volumes and reruns migrations.

## Review Queue

- `GET /review-queue` returns the unified local queue.
- `GET /study-spaces/{id}/review-queue` filters it to one study space.
- Durable learning signals can be completed, dismissed, or snoozed:
  - `POST /learning-signals/{id}/complete`
  - `POST /learning-signals/{id}/dismiss`
  - `POST /learning-signals/{id}/snooze`

If no durable signal exists yet, the queue falls back to deterministic review,
quiz, planner, and unfinished-chapter signals so the product remains useful on a
fresh local database.

## Known Limits

- Study-space import write mode is not implemented; use import dry-run plus whole-app restore for now.
- PDF/OCR/webpage ingestion remain later phases.
- Web search is off unless explicitly enabled and should be treated as supplemental context outside uploaded material.
