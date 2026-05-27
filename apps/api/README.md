# study-agent-api

FastAPI service for study_agent.

## Development

```bash
uv sync
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

## Runtime source ingestion

Local text/Markdown ingestion flow:

1. `POST /api/v1/uploads/presign` with development auth headers.
2. Upload the object to the returned URL.
3. `POST /api/v1/sources/{source_id}/uploaded`.
4. `POST /api/v1/ingestion/sources/{source_id}/run`.
5. Inspect chunks with `GET /api/v1/sources/{source_id}/chunks`.

Runtime ingestion currently supports `text/plain` and `text/markdown` objects. PDF,
OCR, images, and webpage ingestion are intentionally out of scope for this phase.

## Development auth

Protected local endpoints use development headers:

```powershell
$headers = @{
  "X-User-Id" = "<user uuid>"
  "X-Tenant-Id" = "<tenant uuid>"
}
```

The headers are temporary. Production auth will replace them with a proper session/JWT provider while keeping the same `CurrentUserContext` boundary.
