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
$env:PGPASSWORD = "study_agent"
psql -h 127.0.0.1 -p 15432 -U study_agent -d study_agent -c "insert into tenants (id, name) values ('00000000-0000-0000-0000-000000000001', 'Local Tenant') on conflict (id) do nothing; insert into users (id, email, display_name) values ('00000000-0000-0000-0000-000000000002', 'local@example.com', 'Local User') on conflict (id) do nothing; insert into memberships (id, tenant_id, user_id, role) values ('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', 'owner') on conflict (id) do nothing;"
```

## Development auth

Protected local endpoints use development headers:

```powershell
$headers = @{
  "X-User-Id" = "<user uuid>"
  "X-Tenant-Id" = "<tenant uuid>"
}
```

The headers are temporary. Production auth will replace them with a proper session/JWT provider while keeping the same `CurrentUserContext` boundary.
