# Local Lite SQLite Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a no-Docker local mode that runs the app with SQLite and filesystem source storage, while preserving the Docker mode with Postgres, MinIO, and Redis for deployment.

**Architecture:** Introduce explicit runtime profiles: `local` uses SQLite plus `.local/storage`, and `docker` uses Postgres plus MinIO. Keep the application API stable by hiding database/storage differences behind compatibility types, settings, and provider factories. Do not remove Postgres, pgvector, MinIO, or Docker deployment paths.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, SQLite with `aiosqlite`, Postgres with `asyncpg`, Nuxt, Python launcher, Docker Compose.

---

## Runtime Contract

- `python main.py local`
  - Does not start Docker.
  - Uses `sqlite+aiosqlite:///./.local/study_agent.db`.
  - Uses filesystem source storage under `.local/storage/sources`.
  - Runs migrations or creates local schema.
  - Starts API and Web dev servers.
- `python main.py dev`
  - Alias of `local` for day-to-day use.
- `python main.py docker`
  - Starts Docker Compose services for Postgres, Redis, MinIO, API, and Web.
- `python main.py docker-dev`
  - Starts only Docker infrastructure, then runs API/Web on host for debugging.
- `python main.py check`
  - Checks the active local profile.
- `python main.py docker-check`
  - Checks Docker deployment profile.

---

## File Structure

### Backend Compatibility

- Modify `apps/api/pyproject.toml`
  - Add `aiosqlite`.
- Modify `apps/api/app/core/config.py`
  - Add `runtime_profile`.
  - Add `local_database_path`.
  - Add `local_storage_root`.
  - Add `storage_backend`: `s3` or `filesystem`.
  - Keep existing Postgres and S3 settings.
- Modify `apps/api/app/db/session.py`
  - Build engine from settings.
  - Enable SQLite pragmas when the URL starts with `sqlite+aiosqlite`.
- Create `apps/api/app/db/types.py`
  - Provide cross-dialect `GUID`, `JSONDict`, `JSONList`, and `EmbeddingVector`.
- Modify `apps/api/app/db/models.py`
  - Replace direct Postgres-only `UUID`, `JSONB`, and `Vector` imports with compatibility types.
  - Keep enum values unchanged.

### Migrations and Local Schema

- Create `apps/api/app/db/local_schema.py`
  - Provides `create_local_schema(engine)` using `Base.metadata.create_all`.
  - Seeds development tenant/user if missing.
- Modify `apps/api/migrations/env.py`
  - Keep Alembic for Postgres.
  - Skip Postgres-only migrations for SQLite and call local schema creation from `main.py`.
- Keep existing Postgres migration files intact for Docker/deployment.

### Storage

- Modify `apps/api/app/infrastructure/storage.py`
  - Add `FilesystemTextSourceReader`.
  - Add `FilesystemTextSourceWriter`.
  - Factory returns filesystem provider when `storage_backend == "filesystem"`.
- Modify upload/source creation path if needed:
  - Local mode should return a local upload target handled by API, or a paste/source write path.
  - Existing S3 presign remains unchanged for Docker mode.
- Add tests in `apps/api/tests/test_filesystem_storage.py`.

### Retrieval

- Modify `apps/api/app/domain/rag/retrieval.py`
  - Postgres mode can continue using pgvector ordering.
  - SQLite mode should fall back to Python cosine similarity after loading candidate chunks for the study space.
- Add tests in `apps/api/tests/test_rag_retrieval_sqlite.py`.

### Launcher

- Modify `main.py`
  - Add `local`, `docker`, `docker-dev`, and `docker-check`.
  - Make `dev` alias `local`.
  - Local mode sets:
    - `DATABASE_URL=sqlite+aiosqlite:///.../.local/study_agent.db`
    - `STORAGE_BACKEND=filesystem`
    - `LOCAL_STORAGE_ROOT=.local/storage`
  - Docker mode delegates to Docker Compose.
  - Keep existing `backup`, `restore`, and `reset-db` for Docker profile.
  - Add local backup path that copies `.local/study_agent.db` and `.local/storage`.

### Docker

- Modify `infra/docker-compose.yml`
  - Add `api` service.
  - Add `web` service.
  - Keep `postgres`, `redis`, and `minio`.
- Add `apps/api/Dockerfile`.
- Add `apps/web/Dockerfile`.
- Add `.dockerignore`.

### Docs

- Modify `README.md`
  - Explain local lite startup.
  - Explain Docker deployment startup.
  - Explain when Postgres is still used.
- Modify `docs/local-personal-release.md`
  - Add profile matrix: local vs docker.

---

## Task 1: Add Runtime Settings and Dependencies

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/app/core/config.py`
- Test: `apps/api/tests/test_config_profiles.py`

- [ ] Add `aiosqlite` to API dependencies.

- [ ] Add a config test:

```python
from app.core.config import Settings


def test_local_profile_defaults_to_sqlite_and_filesystem() -> None:
    settings = Settings(_env_file=None, runtime_profile="local")
    assert settings.runtime_profile == "local"
    assert settings.storage_backend == "filesystem"
    assert settings.database_url.startswith("sqlite+aiosqlite:///")


def test_docker_profile_keeps_postgres_and_s3() -> None:
    settings = Settings(_env_file=None, runtime_profile="docker")
    assert settings.runtime_profile == "docker"
    assert settings.storage_backend == "s3"
    assert settings.database_url.startswith("postgresql+asyncpg://")
```

- [ ] Implement settings so the tests pass.

- [ ] Run:

```powershell
cd apps\api
uv run pytest tests/test_config_profiles.py -q
```

Expected: tests pass.

---

## Task 2: Add Cross-Dialect SQLAlchemy Types

**Files:**
- Create: `apps/api/app/db/types.py`
- Modify: `apps/api/app/db/models.py`
- Test: `apps/api/tests/test_db_types.py`

- [ ] Add tests that compile model columns for SQLite and Postgres:

```python
from sqlalchemy.dialects import postgresql, sqlite

from app.db.models import SourceChunk


def test_source_chunk_embedding_compiles_for_sqlite_and_postgres() -> None:
    column_type = SourceChunk.__table__.columns["embedding"].type
    assert column_type.compile(dialect=sqlite.dialect())
    assert column_type.compile(dialect=postgresql.dialect())
```

- [ ] Implement `GUID`, JSON aliases, and `EmbeddingVector`.

- [ ] Replace direct model usages:
  - `UUID(as_uuid=True)` -> `GUID()`
  - `JSONB` -> `JSONDict` or `JSONList`
  - `Vector(16)` -> `EmbeddingVector(16)`

- [ ] Run:

```powershell
cd apps\api
uv run pytest tests/test_db_types.py tests/test_quiz_models.py tests/test_space_planner_models.py tests/test_planner_actions_models.py -q
```

Expected: tests pass, adjusting old tests so they assert semantic compatibility instead of direct `JSONB` class identity.

---

## Task 3: Local SQLite Schema Creation

**Files:**
- Create: `apps/api/app/db/local_schema.py`
- Modify: `main.py`
- Test: `apps/api/tests/test_local_schema.py`

- [ ] Write a test that creates a temporary SQLite database and verifies the core tables exist:

```python
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.local_schema import create_local_schema


@pytest.mark.anyio
async def test_create_local_schema_creates_core_tables(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'local.db'}")
    await create_local_schema(engine)
    async with engine.connect() as connection:
        result = await connection.execute(text("select name from sqlite_master where type='table'"))
        tables = {row[0] for row in result}
    assert "study_spaces" in tables
    assert "sources" in tables
    assert "source_chunks" in tables
```

- [ ] Implement `create_local_schema(engine)`.

- [ ] Add dev tenant/user seed helper in the same module.

- [ ] Update `main.py local` to call local schema creation instead of Alembic.

- [ ] Run:

```powershell
cd apps\api
uv run pytest tests/test_local_schema.py -q
```

Expected: tests pass.

---

## Task 4: Filesystem Text Source Storage

**Files:**
- Modify: `apps/api/app/infrastructure/storage.py`
- Test: `apps/api/tests/test_filesystem_storage.py`

- [ ] Add tests:

```python
from app.infrastructure.storage import FilesystemTextSourceReader, FilesystemTextSourceWriter


async def test_filesystem_writer_and_reader_round_trip(tmp_path) -> None:
    writer = FilesystemTextSourceWriter(root=tmp_path, max_bytes=1024)
    reader = FilesystemTextSourceReader(root=tmp_path, max_bytes=1024)
    await writer.write_text("tenant/source.md", "# Local source", "text/markdown")
    result = await reader.read_text("tenant/source.md")
    assert result.text == "# Local source"
    assert result.content_type == "text/markdown"
```

- [ ] Implement filesystem reader/writer.

- [ ] Make factories return filesystem storage when `STORAGE_BACKEND=filesystem`.

- [ ] Run:

```powershell
cd apps\api
uv run pytest tests/test_storage_reader.py tests/test_filesystem_storage.py -q
```

Expected: tests pass.

---

## Task 5: SQLite Retrieval Fallback

**Files:**
- Modify: `apps/api/app/domain/rag/retrieval.py`
- Test: `apps/api/tests/test_rag_retrieval_sqlite.py`

- [ ] Add a unit test that passes candidate chunks and confirms cosine ordering without pgvector.

- [ ] Implement a dialect branch:
  - Postgres keeps vector distance query.
  - SQLite loads recent/candidate chunks for the study space and ranks in Python.

- [ ] Run:

```powershell
cd apps\api
uv run pytest tests/test_rag_retrieval.py tests/test_rag_retrieval_sqlite.py -q
```

Expected: tests pass.

---

## Task 6: Local Launcher Mode

**Files:**
- Modify: `main.py`
- Test: `apps/api/tests/test_main_launcher_profiles.py`

- [ ] Add tests for generated environment:

```python
from pathlib import Path

import main


def test_local_environment_uses_sqlite_and_filesystem(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "ROOT", tmp_path)
    env = main.local_runtime_env()
    assert env["DATABASE_URL"].startswith("sqlite+aiosqlite:///")
    assert env["STORAGE_BACKEND"] == "filesystem"
    assert ".local" in env["LOCAL_STORAGE_ROOT"]
```

- [ ] Implement `local_runtime_env()`.

- [ ] Add subcommands:
  - `local`
  - `docker`
  - `docker-dev`
  - `docker-check`

- [ ] Make `dev` alias `local`.

- [ ] Keep Ctrl+C process cleanup behavior from the current main branch.

- [ ] Run:

```powershell
python -m py_compile main.py
cd apps\api
uv run pytest tests/test_main_launcher_profiles.py -q
```

Expected: tests pass.

---

## Task 7: Docker App Services

**Files:**
- Modify: `infra/docker-compose.yml`
- Create: `apps/api/Dockerfile`
- Create: `apps/web/Dockerfile`
- Create: `.dockerignore`

- [ ] Add `api` service with `DATABASE_URL=postgresql+asyncpg://study_agent:study_agent@postgres:5432/study_agent`.

- [ ] Add `web` service with API base URL pointing at the API service.

- [ ] Ensure `api` depends on Postgres and MinIO.

- [ ] Run:

```powershell
docker compose -f infra/docker-compose.yml config
```

Expected: compose config succeeds.

---

## Task 8: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/local-personal-release.md`

- [ ] Add a startup matrix:

```text
Mode          Command              DB          Source storage       Use
local/dev     python main.py local  SQLite      .local/storage       personal fast startup
docker-dev    python main.py docker-dev Postgres MinIO              host debugging with real infra
docker        python main.py docker Postgres    MinIO                migration/deployment
```

- [ ] Explicitly document that deployed mode still uses Postgres.

- [ ] Add migration note: local SQLite is for personal/local runtime, not the production database.

---

## Task 9: Verification

- [ ] Run API tests:

```powershell
cd apps\api
uv run pytest -q
uv run ruff check app tests
```

- [ ] Run web tests:

```powershell
cd apps\web
npm run test
npm run typecheck
npm run build
```

- [ ] Run launcher checks:

```powershell
python main.py local --skip-install
python main.py check
python main.py docker-check
docker compose -f infra/docker-compose.yml config
```

Expected:
- Local mode starts without Docker.
- Docker mode still uses Postgres/MinIO/Redis.
- Existing API and Web behavior stays compatible.

---

## Self-Review

- Spec coverage: The plan covers local SQLite, filesystem storage, launcher profiles, Docker deployment mode, docs, and verification.
- Placeholder scan: No `TBD` or unresolved placeholder instructions remain.
- Risk: Existing migrations are Postgres-specific. The plan avoids rewriting all historical migrations by using `Base.metadata.create_all` for local SQLite mode and keeping Alembic as the Postgres deployment path.
- Compatibility: Postgres remains the production/deployment database.
