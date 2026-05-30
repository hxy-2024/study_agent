# LeafMind

LeafMind is a local-first AI study workspace that helps your own materials grow
into guided learning routes, grounded mentor answers, quizzes, and review plans.

It is built for personal study: upload Markdown or text notes, generate a route,
study chapter by chapter, ask questions with source citations, and let the Main
Agent suggest what to learn next.

## What It Does

- Creates study spaces around a goal and a set of source materials.
- Ingests Markdown/text sources into searchable chunks with citation metadata.
- Generates learning routes and chapter study pages from your uploaded material.
- Provides a RAG-grounded AI Mentor with expandable citations and source jumps.
- Tracks chapter mentor state, weak points, quiz mastery, and planner actions.
- Recommends what to study next through a Main Agent dashboard signal pipeline.
- Supports quiz retakes, review queues, local AI settings, and optional web search.
- Exports study spaces and supports local backup/restore for personal data safety.

## Agent Model

LeafMind uses a layered agent design:

- **L1 Main Agent** decides the next learning move from time, intent, route state,
  review signals, quiz mastery, and planner actions.
- **L2 Planning Agents** summarize progress, weak points, route risks, review
  candidates, and planner actions.
- **L3 Session Tutor** handles chapter-level RAG chat. LangGraph is used here for
  multi-step tutoring: load context, save messages, retrieve evidence, optionally
  use web search, generate an answer, save citations, and record learning signals.

The Main Agent is currently deterministic by design. LangGraph should move upward
only when L1 needs multi-step planning, tool use, confirmations, and resumable
state.

## Tech Stack

- **Frontend:** Nuxt, Vue, Pinia, Vitest
- **Backend:** FastAPI, SQLAlchemy, Alembic, Pydantic
- **AI/RAG:** local deterministic providers, OpenAI-compatible LLM option,
  LangGraph for Session Tutor runtime
- **Storage:** SQLite for fast local mode, Postgres + pgvector + MinIO for
  Docker-backed mode
- **Runtime:** Python launcher, Docker Compose, local file storage

## Quick Start

Prerequisites:

- Python 3.12
- `uv`
- Node.js 20+
- Docker Desktop, only for Docker-backed mode

Start the local personal runtime:

```powershell
cd F:\AIproject\study_agent
python main.py local
```

`python main.py dev` is an alias for local mode.

Open:

```text
http://127.0.0.1:3000
```

The local profile uses SQLite and local file storage under `.local/`, so it is
the fastest way to try the product.

## Docker-Backed Runtime

Use this when you want Postgres, pgvector, Redis, and MinIO locally:

```powershell
python main.py docker-dev
```

Deployment-style Compose startup:

```powershell
docker compose -f infra/docker-compose.yml up --build
```

Default local ports:

| Service | URL |
| --- | --- |
| Web | `http://127.0.0.1:3000` |
| API | `http://127.0.0.1:8000` |
| Postgres | `localhost:15432` |
| Redis | `localhost:6379` |
| MinIO API | `http://localhost:9000` |
| MinIO Console | `http://localhost:9001` |

## Typical Workflow

1. Create a study space.
2. Upload or paste a Markdown/text source.
3. Run ingestion.
4. Generate a learning route.
5. Open a chapter and study the evidence.
6. Ask the AI Mentor questions and inspect citations.
7. Generate and submit quizzes.
8. Review weak points and retake quizzes when needed.
9. Use the Home dashboard to follow the Main Agent recommendation.

## AI Settings

LeafMind works without an external LLM key by using deterministic local answer
providers. To use an OpenAI-compatible chat completion API, configure:

```env
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=30
```

You can also configure provider, model, API key, answer style, and default web
search behavior from the local settings panel. API keys are stored under
`.local/` and ignored by git.

Web search is explicit. When enabled, it is treated as supplemental network
context, not as uploaded source material.

## Data Safety

Create a local backup:

```powershell
python main.py backup --dry-run
python main.py backup
```

Restore a backup:

```powershell
python main.py restore .local\backups\local-YYYYMMDD-HHMMSS
python main.py restore .local\backups\local-YYYYMMDD-HHMMSS --yes
```

Reset local Docker data:

```powershell
python main.py reset-db
python main.py reset-db --yes
```

Study spaces can also be exported as JSON or Markdown from the app.

## Development

Run API checks:

```powershell
cd apps\api
uv run pytest -q
uv run ruff check app tests
```

Run web checks:

```powershell
cd apps\web
npm run test
npm run typecheck
npm run build
```

Run local environment checks:

```powershell
python main.py check
python main.py docker-check
```

## Current Limits

- Runtime ingestion currently targets Markdown and text sources.
- PDF, OCR, webpage ingestion, and full write-mode study-space import are later
  phases.
- The product is currently optimized for local personal use, not hosted
  multi-user deployment.
- The local SQLite profile is for personal runtime only; Docker-backed Postgres
  remains the closer deployment shape.

## License

No license has been selected yet.
