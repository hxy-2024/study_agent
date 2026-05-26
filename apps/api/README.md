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
uv run pytest tests/test_rag_chunking.py tests/test_rag_embeddings.py tests/test_rag_ingestion.py tests/test_rag_ingestion_integration.py tests/test_rag_retrieval.py tests/test_ingestion_routes.py -q
```

Guarded Postgres tests require `RUN_POSTGRES_TESTS=1` and `DATABASE_URL`.
