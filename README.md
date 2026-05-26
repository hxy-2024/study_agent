# study_agent

AI learning agent platform.

## Current Implementation Scope

The current foundation includes:

- Local Postgres, Redis, and MinIO infrastructure.
- FastAPI API service.
- Tenant-aware study space and source metadata models.
- Study space creation API.
- Upload presign API.
- Nuxt app shell.
- Dashboard and create-space UI.

LangGraph agents, streaming chat, quizzes, mastery tracking, and import/export are planned as separate implementation phases.

### RAG foundation

The API includes the first RAG foundation:

- uploaded source metadata can be ingested into chunks;
- chunks store citation metadata and embeddings;
- retrieval is scoped by tenant and study space;
- deterministic embeddings are used for local development and tests.

The first runtime ingestion endpoint exposes the API shape but returns `501` until object-storage text reading is configured. Domain tests cover the ingestion path with an in-memory text reader.

## Local Development

```bash
cp .env.example apps/api/.env
make infra-up
cd apps/api && uv sync && uv run alembic upgrade head
make api-run
```

In another terminal:

```bash
cd apps/web
npm install
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

Open `http://localhost:3000`.
