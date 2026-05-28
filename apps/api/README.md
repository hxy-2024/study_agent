# study-agent-api

FastAPI service for study_agent.

## Development

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest -q
```

## RAG domain

The RAG foundation lives in:

- `app/domain/rag/chunking.py`
- `app/domain/rag/embeddings.py`
- `app/domain/rag/ingestion.py`
- `app/domain/rag/retrieval.py`

Run the focused RAG test suite with:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_rag_chunking.py tests/test_rag_embeddings.py tests/test_rag_ingestion.py tests/test_rag_ingestion_integration.py tests/test_rag_retrieval.py tests/test_ingestion_routes.py tests/test_runtime_ingestion_route.py -q
```

Guarded Postgres tests require `RUN_POSTGRES_TESTS=1` and `DATABASE_URL`.

Runtime RAG endpoints are guarded by development auth headers backed by tenant
membership.

## Chapter mentor LLM provider

`POST /api/v1/chapters/{chapter_id}/mentor/questions` retrieves tenant-scoped
chapter evidence first, then asks the configured answer provider to compose the
final response. The default provider is deterministic and does not call the
network.

OpenAI-compatible runtime configuration:

```env
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=30
```

When `LLM_API_KEY` is empty, the API falls back to the deterministic provider.

## Chapter mentor state

The Chapter Mentor State Agent aggregates tutor sessions for one chapter into a
durable chapter-level assessment.

Endpoints:

- `GET /api/v1/chapters/{chapter_id}/mentor-state`
- `POST /api/v1/agents/chapter-summary/run`

The run endpoint uses `CurrentUserContext` for tenant scope and rejects
client-supplied tenant IDs. Each run records an `agent_runs` row with
`agent_type=chapter_mentor`. Local generation is deterministic for repeatable
tests and can be replaced behind the domain service boundary later.

## Quiz + mastery

The quiz domain adds deterministic user-scoped chapter quizzes and mastery records.

Endpoints:

- `POST /api/v1/chapters/{chapter_id}/quizzes/generate`
- `GET /api/v1/quizzes/{quiz_id}`
- `POST /api/v1/quizzes/{quiz_id}/submit`
- `GET /api/v1/quizzes/{quiz_id}/result`
- `GET /api/v1/chapters/{chapter_id}/mastery`

Generation is deterministic in this phase. Quiz submissions update the current
user's latest chapter mastery record; review cards, spaced repetition, and LLM
quiz generation are separate later phases.

## Runtime source ingestion

Local text/Markdown ingestion flow:

1. `POST /api/v1/uploads/presign` with development auth headers.
2. Upload the object to the returned URL.
3. `POST /api/v1/sources/{source_id}/uploaded`.
4. `POST /api/v1/ingestion/sources/{source_id}/run`.
5. Inspect chunks with `GET /api/v1/sources/{source_id}/chunks`.

Runtime ingestion currently supports `text/plain` and `text/markdown` objects. PDF,
OCR, images, and webpage ingestion are intentionally out of scope for this phase.

## Local infrastructure

The Docker Compose Postgres service publishes container port `5432` on host port
`15432` to avoid conflicts with a locally installed PostgreSQL server. The default
`DATABASE_URL` is:

```text
postgresql+asyncpg://study_agent:study_agent@localhost:15432/study_agent
```

When using development auth, seed the local tenant/user/membership once:

```powershell
cd F:\AIproject\study_agent
make api-seed-dev
```

With the API and infrastructure running, execute the local API smoke flow:

```powershell
cd F:\AIproject\study_agent
make api-smoke-local
```

The smoke flow creates a study space, uploads a Markdown source through MinIO,
runs ingestion, generates a route, asks the chapter mentor, and completes the
chapter.

## Development auth

Protected local endpoints use development headers:

```powershell
$headers = @{
  "X-User-Id" = "<user uuid>"
  "X-Tenant-Id" = "<tenant uuid>"
}
```

The headers are temporary. Production auth will replace them with a proper session/JWT provider while keeping the same `CurrentUserContext` boundary.
