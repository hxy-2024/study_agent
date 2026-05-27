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

Runtime ingestion supports text and Markdown objects in S3-compatible storage after a source is marked uploaded. PDF, OCR, and webpage ingestion remain later phases. Runtime retrieval is enabled only when the request includes valid development auth headers and the user is a member of the tenant. Domain tests cover ingestion and retrieval with local providers.

### AI Mentor answer provider

Chapter AI Mentor uses RAG retrieval for grounding. By default it uses a deterministic
local answer provider, so the app works without an external LLM key. To use an
OpenAI-compatible chat completion API, set:

```env
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=30
```

The same interface can point at other OpenAI-compatible providers by changing
`LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.

### Development auth headers

Local protected API calls use development headers until the full login flow is implemented:

- `X-User-Id`: existing user UUID
- `X-Tenant-Id`: existing tenant UUID

The API verifies membership before returning tenant-scoped data.

## Local Development

Prerequisites:

- Docker Desktop running.
- Python 3.12 with `uv`.
- Node.js 20+.

The local stack uses these ports:

- Web: `http://127.0.0.1:3000`
- API: `http://127.0.0.1:8000`
- Postgres: `localhost:15432`
- Redis: `localhost:6379`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`

Start infrastructure:

```powershell
cd F:\AIproject\study_agent
docker compose -f infra/docker-compose.yml up -d postgres redis minio
```

Prepare the API database:

```powershell
cd F:\AIproject\study_agent\apps\api
uv sync
uv run alembic upgrade head
```

Seed the temporary development auth identity:

```powershell
$env:PGPASSWORD = "study_agent"
psql -h 127.0.0.1 -p 15432 -U study_agent -d study_agent -c "insert into tenants (id, name) values ('00000000-0000-0000-0000-000000000001', 'Local Tenant') on conflict (id) do nothing; insert into users (id, email, display_name) values ('00000000-0000-0000-0000-000000000002', 'local@example.com', 'Local User') on conflict (id) do nothing; insert into memberships (id, tenant_id, user_id, role) values ('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', 'owner') on conflict (id) do nothing;"
```

Start the API:

```powershell
cd F:\AIproject\study_agent\apps\api
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the web app in another terminal:

```powershell
cd apps/web
npm install
npm run dev -- --host 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`.

Manual smoke test:

1. Create a study space.
2. Upload a `.md` source.
3. Run ingestion.
4. Generate a route.
5. Open a chapter with `Study`.
6. Mark the chapter complete.
