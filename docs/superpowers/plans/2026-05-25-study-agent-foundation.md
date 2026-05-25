# Study Agent Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executable foundation for study_agent: project scaffold, API service, database models, study space creation, source upload metadata, and a Nuxt app shell with dashboard and create-space flow.

**Architecture:** Use a Production Modular Monolith foundation. The repo contains `apps/api` for FastAPI, `apps/web` for Nuxt/Vue, and `infra` for local Docker Compose dependencies. This plan does not implement RAG, LangGraph, streaming chat, quizzes, or production auth; those are separate plans after the foundation is running.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x async, Alembic, Postgres with pgvector extension enabled, Redis, MinIO, Nuxt 4, Vue 3, TypeScript, Tailwind CSS, Pinia, Vitest, Playwright, Docker Compose.

---

## Scope Check

The approved spec covers multiple subsystems: foundation, RAG, agent orchestration, chat, quizzes, mastery, import/export, observability, and enterprise controls. This plan implements only the foundation and Phase 1 surface. It must leave clean interfaces for later plans:

- `apps/api/app/domain/sources` stores source metadata but does not parse or embed files.
- `apps/api/app/domain/agents` contains no LangGraph implementation in this plan.
- `apps/api/app/domain/rag` is represented only by table readiness through `source_chunks`.
- `apps/web` shows navigation and creation flows but does not implement chat or quiz pages.

## File Structure

Create this structure:

```text
apps/
  api/
    pyproject.toml
    README.md
    alembic.ini
    app/
      __init__.py
      main.py
      core/config.py
      core/security.py
      core/time.py
      db/base.py
      db/session.py
      db/models.py
      api/router.py
      api/routes_health.py
      api/routes_study_spaces.py
      api/routes_uploads.py
      domain/study_spaces/schemas.py
      domain/study_spaces/service.py
      domain/sources/schemas.py
      domain/sources/service.py
      infrastructure/storage.py
    migrations/
      env.py
      versions/0001_foundation.py
    tests/
      conftest.py
      test_health.py
      test_study_spaces.py
      test_uploads.py
  web/
    package.json
    nuxt.config.ts
    app.vue
    assets/css/main.css
    pages/index.vue
    pages/spaces/new.vue
    pages/spaces/[id]/index.vue
    stores/studySpaces.ts
    tests/create-space.spec.ts
infra/
  docker-compose.yml
  postgres/init/001_extensions.sql
.env.example
Makefile
```

Responsibilities:

- `apps/api/app/main.py`: FastAPI app factory and middleware registration.
- `apps/api/app/core/config.py`: environment settings.
- `apps/api/app/db/models.py`: tenant-aware SQLAlchemy models used in this foundation.
- `apps/api/app/domain/study_spaces/service.py`: study space business rules.
- `apps/api/app/domain/sources/service.py`: source metadata and upload request rules.
- `apps/api/app/infrastructure/storage.py`: presigned upload abstraction.
- `apps/web/pages`: user-facing app shell, dashboard, create-space, and placeholder space home.

---

### Task 1: Repository Foundation

**Files:**
- Create: `.env.example`
- Create: `Makefile`
- Create: `infra/docker-compose.yml`
- Create: `infra/postgres/init/001_extensions.sql`
- Modify: `.gitignore`

- [ ] **Step 1: Write the environment template**

Create `.env.example`:

```env
POSTGRES_USER=study_agent
POSTGRES_PASSWORD=study_agent
POSTGRES_DB=study_agent
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://study_agent:study_agent@localhost:5432/study_agent
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT_URL=http://localhost:9000
S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET=study-agent-local
API_CORS_ORIGINS=http://localhost:3000
```

- [ ] **Step 2: Write local infrastructure**

Create `infra/docker-compose.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: study_agent
      POSTGRES_PASSWORD: study_agent
      POSTGRES_DB: study_agent
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./postgres/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U study_agent -d study_agent"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio:RELEASE.2025-04-22T22-12-26Z
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/data

volumes:
  postgres-data:
  minio-data:
```

Create `infra/postgres/init/001_extensions.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

- [ ] **Step 3: Write developer commands**

Create `Makefile`:

```makefile
.PHONY: infra-up infra-down api-test api-run web-install web-dev web-test

infra-up:
	docker compose -f infra/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker-compose.yml down

api-test:
	cd apps/api && uv run pytest -q

api-run:
	cd apps/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web-install:
	cd apps/web && npm install

web-dev:
	cd apps/web && npm run dev

web-test:
	cd apps/web && npm run test
```

- [ ] **Step 4: Update `.gitignore`**

Ensure `.gitignore` contains:

```gitignore
.superpowers/
.env
.venv/
__pycache__/
.pytest_cache/
node_modules/
.nuxt/
.output/
dist/
coverage/
```

- [ ] **Step 5: Verify infrastructure config**

Run:

```bash
docker compose -f infra/docker-compose.yml config
```

Expected: exit 0 and printed normalized Compose config.

- [ ] **Step 6: Commit**

```bash
git add .env.example .gitignore Makefile infra/docker-compose.yml infra/postgres/init/001_extensions.sql
git commit -m "chore: add local infrastructure foundation"
```

---

### Task 2: FastAPI Project Skeleton

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/README.md`
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/core/config.py`
- Create: `apps/api/app/api/router.py`
- Create: `apps/api/app/api/routes_health.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Write the failing health test**

Create `apps/api/tests/test_health.py`:

```python
from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_returns_ok() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "study-agent-api"}
```

- [ ] **Step 2: Add API dependencies**

Create `apps/api/pyproject.toml`:

```toml
[project]
name = "study-agent-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1.13.0",
  "asyncpg>=0.29.0",
  "boto3>=1.34.0",
  "fastapi>=0.115.0",
  "greenlet>=3.0.0",
  "httpx>=0.27.0",
  "pydantic-settings>=2.6.0",
  "python-multipart>=0.0.12",
  "sqlalchemy>=2.0.0",
  "uvicorn[standard]>=0.30.0"
]

[dependency-groups]
dev = [
  "pytest>=8.3.0",
  "pytest-asyncio>=0.24.0",
  "ruff>=0.7.0"
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 3: Implement settings**

Create `apps/api/app/core/config.py`:

```python
from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "study-agent-api"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://study_agent:study_agent@localhost:5432/study_agent"
    redis_url: str = "redis://localhost:6379/0"
    api_cors_origins: list[AnyHttpUrl] = []
    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "study-agent-local"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Implement API router and health route**

Create `apps/api/app/api/routes_health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "study-agent-api"}
```

Create `apps/api/app/api/router.py`:

```python
from fastapi import APIRouter

from app.api import routes_health

api_router = APIRouter()
api_router.include_router(routes_health.router)
```

Create `apps/api/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.api_cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
```

Create `apps/api/app/__init__.py`:

```python
__all__ = ["main"]
```

- [ ] **Step 5: Add test README and conftest**

Create `apps/api/tests/conftest.py`:

```python
import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
```

Create `apps/api/README.md`:

```markdown
# study-agent-api

FastAPI service for study_agent.

## Development

```bash
uv sync
uv run uvicorn app.main:app --reload
uv run pytest -q
```
```

- [ ] **Step 6: Run health test**

Run:

```bash
cd apps/api && uv run pytest tests/test_health.py -q
```

Expected: `1 passed`.

- [ ] **Step 7: Commit**

```bash
git add apps/api
git commit -m "feat(api): add fastapi foundation"
```

---

### Task 3: Database Models and Migration

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/app/db/base.py`
- Create: `apps/api/app/db/session.py`
- Create: `apps/api/app/db/models.py`
- Create: `apps/api/migrations/env.py`
- Create: `apps/api/migrations/versions/0001_foundation.py`
- Create: `apps/api/tests/test_models.py`

- [ ] **Step 1: Write model metadata test**

Create `apps/api/tests/test_models.py`:

```python
from app.db.models import StudySpace, Source, Tenant, User


def test_core_tables_are_tenant_aware() -> None:
    assert Tenant.__tablename__ == "tenants"
    assert User.__tablename__ == "users"
    assert StudySpace.__tablename__ == "study_spaces"
    assert Source.__tablename__ == "sources"
    assert "tenant_id" in StudySpace.__table__.columns
    assert "tenant_id" in Source.__table__.columns
```

- [ ] **Step 2: Implement database base and session**

Create `apps/api/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Create `apps/api/app/db/session.py`:

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 3: Implement foundation models**

Create `apps/api/app/db/models.py`:

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudySpaceStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class SourceStatus(str, enum.Enum):
    pending_upload = "pending_upload"
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="owner")


class StudySpace(Base):
    __tablename__ = "study_spaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(60), nullable=False, default="beginner")
    intensity: Mapped[str] = mapped_column(String(60), nullable=False, default="normal")
    target_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[StudySpaceStatus] = mapped_column(
        Enum(StudySpaceStatus, name="study_space_status"),
        nullable=False,
        default=StudySpaceStatus.active,
    )
    route_outline: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sources: Mapped[list["Source"]] = relationship(back_populates="study_space")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_spaces.id"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus, name="source_status"),
        nullable=False,
        default=SourceStatus.pending_upload,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study_space: Mapped[StudySpace] = relationship(back_populates="sources")
```

- [ ] **Step 4: Add Alembic config**

Create `apps/api/alembic.ini`:

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://study_agent:study_agent@localhost:5432/study_agent

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `apps/api/migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("+asyncpg", ""))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: Add initial migration**

Create `apps/api/migrations/versions/0001_foundation.py` with tables matching `models.py`. Use explicit enum creation and `op.create_table` for `tenants`, `users`, `memberships`, `study_spaces`, and `sources`. Include indexes on tenant and owner fields. The generated revision id must be:

```python
revision = "0001_foundation"
down_revision = None
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd apps/api && uv run pytest tests/test_models.py -q
```

Expected: `1 passed`.

- [ ] **Step 7: Commit**

```bash
git add apps/api/alembic.ini apps/api/app/db apps/api/migrations apps/api/tests/test_models.py
git commit -m "feat(api): add tenant aware foundation models"
```

---

### Task 4: Study Space API

**Files:**
- Create: `apps/api/app/domain/study_spaces/schemas.py`
- Create: `apps/api/app/domain/study_spaces/service.py`
- Create: `apps/api/app/api/routes_study_spaces.py`
- Modify: `apps/api/app/api/router.py`
- Create: `apps/api/tests/test_study_spaces.py`

- [ ] **Step 1: Write API tests**

Create `apps/api/tests/test_study_spaces.py`:

```python
import uuid

from app.domain.study_spaces.service import create_route_outline


def test_create_route_outline_uses_goal_when_no_ai_is_available() -> None:
    outline = create_route_outline(goal="Learn linear algebra", target_days=14)

    assert outline[0]["title"] == "学习目标梳理"
    assert outline[0]["description"] == "明确 Learn linear algebra 的学习范围、已有基础和完成标准。"
    assert outline[-1]["title"] == "综合复习与测评"


def test_study_space_payload_contains_tenant_fields() -> None:
    tenant_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()

    payload = {
        "tenant_id": tenant_id,
        "owner_user_id": owner_user_id,
        "name": "Linear Algebra",
        "goal": "Understand matrices",
        "level": "beginner",
        "intensity": "normal",
        "target_days": 30,
    }

    assert payload["tenant_id"] == tenant_id
    assert payload["owner_user_id"] == owner_user_id
```

- [ ] **Step 2: Implement schemas**

Create `apps/api/app/domain/study_spaces/schemas.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RouteChapter(BaseModel):
    order: int
    title: str
    description: str
    estimated_days: int


class StudySpaceCreate(BaseModel):
    tenant_id: uuid.UUID
    owner_user_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    goal: str = Field(min_length=1, max_length=4000)
    level: str = Field(default="beginner", max_length=60)
    intensity: str = Field(default="normal", max_length=60)
    target_days: int = Field(default=30, ge=1, le=365)


class StudySpaceRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    owner_user_id: uuid.UUID
    name: str
    goal: str
    level: str
    intensity: str
    target_days: int
    status: str
    route_outline: list[RouteChapter]
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Implement route generation fallback and service**

Create `apps/api/app/domain/study_spaces/service.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudySpace
from app.domain.study_spaces.schemas import StudySpaceCreate


def create_route_outline(goal: str, target_days: int) -> list[dict]:
    first_block = max(1, target_days // 4)
    middle_block = max(1, target_days // 2)
    final_block = max(1, target_days - first_block - middle_block)
    return [
        {
            "order": 1,
            "title": "学习目标梳理",
            "description": f"明确 {goal} 的学习范围、已有基础和完成标准。",
            "estimated_days": first_block,
        },
        {
            "order": 2,
            "title": "核心概念学习",
            "description": "围绕资料和目标拆解关键概念，建立基础知识结构。",
            "estimated_days": middle_block,
        },
        {
            "order": 3,
            "title": "综合复习与测评",
            "description": "通过小测、错题和复习卡片检查掌握情况。",
            "estimated_days": final_block,
        },
    ]


async def create_study_space(session: AsyncSession, payload: StudySpaceCreate) -> StudySpace:
    study_space = StudySpace(
        tenant_id=payload.tenant_id,
        owner_user_id=payload.owner_user_id,
        name=payload.name,
        goal=payload.goal,
        level=payload.level,
        intensity=payload.intensity,
        target_days=payload.target_days,
        route_outline=create_route_outline(payload.goal, payload.target_days),
    )
    session.add(study_space)
    await session.commit()
    await session.refresh(study_space)
    return study_space


async def list_study_spaces(session: AsyncSession, tenant_id) -> list[StudySpace]:
    result = await session.execute(
        select(StudySpace)
        .where(StudySpace.tenant_id == tenant_id)
        .order_by(StudySpace.created_at.desc())
    )
    return list(result.scalars().all())
```

- [ ] **Step 4: Implement routes**

Create `apps/api/app/api/routes_study_spaces.py`:

```python
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.domain.study_spaces.schemas import StudySpaceCreate, StudySpaceRead
from app.domain.study_spaces.service import create_study_space, list_study_spaces

router = APIRouter(prefix="/study-spaces", tags=["study-spaces"])


@router.get("", response_model=list[StudySpaceRead])
async def list_spaces(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list:
    return await list_study_spaces(session, tenant_id)


@router.post("", response_model=StudySpaceRead, status_code=201)
async def create_space(
    payload: StudySpaceCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await create_study_space(session, payload)
```

Modify `apps/api/app/api/router.py`:

```python
from fastapi import APIRouter

from app.api import routes_health, routes_study_spaces

api_router = APIRouter()
api_router.include_router(routes_health.router)
api_router.include_router(routes_study_spaces.router)
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd apps/api && uv run pytest tests/test_study_spaces.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/domain/study_spaces apps/api/app/api/routes_study_spaces.py apps/api/app/api/router.py apps/api/tests/test_study_spaces.py
git commit -m "feat(api): add study space creation"
```

---

### Task 5: Upload Metadata API

**Files:**
- Create: `apps/api/app/domain/sources/schemas.py`
- Create: `apps/api/app/domain/sources/service.py`
- Create: `apps/api/app/infrastructure/storage.py`
- Create: `apps/api/app/api/routes_uploads.py`
- Modify: `apps/api/app/api/router.py`
- Create: `apps/api/tests/test_uploads.py`

- [ ] **Step 1: Write upload validation tests**

Create `apps/api/tests/test_uploads.py`:

```python
import uuid

import pytest

from app.domain.sources.service import build_object_key, validate_content_type


def test_build_object_key_is_tenant_and_space_scoped() -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    space_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    object_key = build_object_key(tenant_id, space_id, "algebra notes.pdf")

    assert object_key.startswith("tenants/00000000-0000-0000-0000-000000000001/")
    assert "/spaces/00000000-0000-0000-0000-000000000002/sources/" in object_key
    assert object_key.endswith("/algebra-notes.pdf")


def test_validate_content_type_accepts_supported_types() -> None:
    validate_content_type("application/pdf")
    validate_content_type("image/png")
    validate_content_type("text/markdown")


def test_validate_content_type_rejects_unsupported_types() -> None:
    with pytest.raises(ValueError, match="Unsupported content type"):
        validate_content_type("application/x-msdownload")
```

- [ ] **Step 2: Implement source schemas**

Create `apps/api/app/domain/sources/schemas.py`:

```python
import uuid

from pydantic import BaseModel, Field


class UploadPresignRequest(BaseModel):
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)


class UploadPresignResponse(BaseModel):
    source_id: uuid.UUID
    object_key: str
    upload_url: str
    method: str = "PUT"
```

- [ ] **Step 3: Implement storage abstraction**

Create `apps/api/app/infrastructure/storage.py`:

```python
import boto3

from app.core.config import get_settings


def create_presigned_put_url(object_key: str, content_type: str) -> str:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )
    return client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=900,
    )
```

- [ ] **Step 4: Implement source service**

Create `apps/api/app/domain/sources/service.py`:

```python
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source
from app.domain.sources.schemas import UploadPresignRequest
from app.infrastructure.storage import create_presigned_put_url

SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
    "text/markdown",
}


def validate_content_type(content_type: str) -> None:
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}")


def slugify_filename(filename: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", filename.strip()).strip("-")
    return cleaned or "source"


def build_object_key(tenant_id: uuid.UUID, study_space_id: uuid.UUID, filename: str) -> str:
    source_id = uuid.uuid4()
    safe_name = slugify_filename(filename)
    return f"tenants/{tenant_id}/spaces/{study_space_id}/sources/{source_id}/{safe_name}"


async def create_upload_request(session: AsyncSession, payload: UploadPresignRequest) -> tuple[Source, str]:
    validate_content_type(payload.content_type)
    object_key = build_object_key(payload.tenant_id, payload.study_space_id, payload.filename)
    source = Source(
        tenant_id=payload.tenant_id,
        study_space_id=payload.study_space_id,
        filename=payload.filename,
        content_type=payload.content_type,
        object_key=object_key,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    upload_url = create_presigned_put_url(object_key=object_key, content_type=payload.content_type)
    return source, upload_url
```

- [ ] **Step 5: Implement upload route**

Create `apps/api/app/api/routes_uploads.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.domain.sources.schemas import UploadPresignRequest, UploadPresignResponse
from app.domain.sources.service import create_upload_request

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/presign", response_model=UploadPresignResponse)
async def presign_upload(
    payload: UploadPresignRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UploadPresignResponse:
    try:
        source, upload_url = await create_upload_request(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadPresignResponse(
        source_id=source.id,
        object_key=source.object_key,
        upload_url=upload_url,
    )
```

Modify `apps/api/app/api/router.py`:

```python
from fastapi import APIRouter

from app.api import routes_health, routes_study_spaces, routes_uploads

api_router = APIRouter()
api_router.include_router(routes_health.router)
api_router.include_router(routes_study_spaces.router)
api_router.include_router(routes_uploads.router)
```

- [ ] **Step 6: Run upload tests**

Run:

```bash
cd apps/api && uv run pytest tests/test_uploads.py -q
```

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/domain/sources apps/api/app/infrastructure apps/api/app/api/routes_uploads.py apps/api/app/api/router.py apps/api/tests/test_uploads.py
git commit -m "feat(api): add source upload presign endpoint"
```

---

### Task 6: Nuxt App Shell

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/nuxt.config.ts`
- Create: `apps/web/app.vue`
- Create: `apps/web/assets/css/main.css`
- Create: `apps/web/pages/index.vue`
- Create: `apps/web/stores/studySpaces.ts`

- [ ] **Step 1: Create package manifest**

Create `apps/web/package.json`:

```json
{
  "name": "study-agent-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "nuxt dev",
    "build": "nuxt build",
    "test": "vitest run",
    "typecheck": "vue-tsc --noEmit"
  },
  "dependencies": {
    "@pinia/nuxt": "^0.9.0",
    "nuxt": "^4.0.0",
    "pinia": "^2.3.0",
    "vue": "^3.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.0",
    "typescript": "^5.7.0",
    "vitest": "^2.1.0",
    "vue-tsc": "^2.1.0"
  }
}
```

- [ ] **Step 2: Configure Nuxt**

Create `apps/web/nuxt.config.ts`:

```ts
export default defineNuxtConfig({
  modules: ['@pinia/nuxt'],
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'
    }
  },
  typescript: {
    strict: true
  }
})
```

- [ ] **Step 3: Add app shell styles**

Create `apps/web/assets/css/main.css`:

```css
:root {
  color: #172033;
  background: #f6f8fb;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

body {
  margin: 0;
}

button,
input,
textarea,
select {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 240px 1fr;
}

.sidebar {
  background: #111827;
  color: #f8fafc;
  padding: 20px 16px;
}

.main {
  padding: 24px;
}

.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.primary-button {
  border: 0;
  border-radius: 8px;
  padding: 10px 14px;
  background: #2563eb;
  color: white;
  cursor: pointer;
}

.card {
  border: 1px solid #d8dee9;
  border-radius: 8px;
  background: white;
  padding: 16px;
}
```

- [ ] **Step 4: Create root layout**

Create `apps/web/app.vue`:

```vue
<template>
  <div class="app-shell">
    <aside class="sidebar">
      <strong>study_agent</strong>
      <nav style="display: grid; gap: 12px; margin-top: 24px;">
        <NuxtLink to="/">学习空间</NuxtLink>
        <NuxtLink to="/">待复习</NuxtLink>
        <NuxtLink to="/">资料库</NuxtLink>
        <NuxtLink to="/">学习画像</NuxtLink>
      </nav>
    </aside>
    <main class="main">
      <NuxtPage />
    </main>
  </div>
</template>
```

- [ ] **Step 5: Add store and dashboard page**

Create `apps/web/stores/studySpaces.ts`:

```ts
import { defineStore } from 'pinia'

export interface StudySpace {
  id: string
  name: string
  goal: string
  status: string
  target_days: number
}

export const useStudySpacesStore = defineStore('studySpaces', {
  state: () => ({
    spaces: [] as StudySpace[],
    loading: false
  }),
  actions: {
    async loadSpaces() {
      const config = useRuntimeConfig()
      this.loading = true
      try {
        this.spaces = await $fetch<StudySpace[]>(`${config.public.apiBaseUrl}/study-spaces`, {
          query: { tenant_id: '00000000-0000-0000-0000-000000000001' }
        })
      } finally {
        this.loading = false
      }
    }
  }
})
```

Create `apps/web/pages/index.vue`:

```vue
<script setup lang="ts">
const store = useStudySpacesStore()

onMounted(() => {
  store.loadSpaces()
})
</script>

<template>
  <section>
    <div class="topbar">
      <div>
        <h1>学习空间</h1>
        <p>继续学习、查看待复习内容，或创建新的学习计划。</p>
      </div>
      <NuxtLink class="primary-button" to="/spaces/new">新建学习空间</NuxtLink>
    </div>

    <div v-if="store.loading" class="card">正在加载学习空间...</div>
    <div v-else-if="store.spaces.length === 0" class="card">
      <h2>还没有学习空间</h2>
      <p>创建一个学习空间，上传教材并生成学习路线。</p>
      <NuxtLink class="primary-button" to="/spaces/new">开始创建</NuxtLink>
    </div>
    <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px;">
      <NuxtLink v-for="space in store.spaces" :key="space.id" class="card" :to="`/spaces/${space.id}`">
        <h2>{{ space.name }}</h2>
        <p>{{ space.goal }}</p>
        <small>{{ space.status }} · {{ space.target_days }} 天</small>
      </NuxtLink>
    </div>
  </section>
</template>
```

- [ ] **Step 6: Run front-end install and typecheck**

Run:

```bash
cd apps/web && npm install && npm run typecheck
```

Expected: install completes and `vue-tsc` exits 0.

- [ ] **Step 7: Commit**

```bash
git add apps/web
git commit -m "feat(web): add nuxt app shell"
```

---

### Task 7: Create Study Space UI

**Files:**
- Create: `apps/web/pages/spaces/new.vue`
- Create: `apps/web/pages/spaces/[id]/index.vue`
- Create: `apps/web/tests/create-space.spec.ts`
- Modify: `apps/web/package.json`

- [ ] **Step 1: Add create page**

Create `apps/web/pages/spaces/new.vue`:

```vue
<script setup lang="ts">
const config = useRuntimeConfig()
const router = useRouter()

const form = reactive({
  name: '',
  goal: '',
  level: 'beginner',
  intensity: 'normal',
  target_days: 30
})

const routeOutline = ref<Array<{ order: number; title: string; description: string; estimated_days: number }>>([])
const submitting = ref(false)
const errorMessage = ref('')

function renderDraftRoute() {
  const first = Math.max(1, Math.floor(form.target_days / 4))
  const second = Math.max(1, Math.floor(form.target_days / 2))
  const third = Math.max(1, form.target_days - first - second)
  routeOutline.value = [
    {
      order: 1,
      title: '学习目标梳理',
      description: `明确 ${form.goal || '当前目标'} 的学习范围、已有基础和完成标准。`,
      estimated_days: first
    },
    {
      order: 2,
      title: '核心概念学习',
      description: '围绕资料和目标拆解关键概念，建立基础知识结构。',
      estimated_days: second
    },
    {
      order: 3,
      title: '综合复习与测评',
      description: '通过小测、错题和复习卡片检查掌握情况。',
      estimated_days: third
    }
  ]
}

async function createSpace() {
  submitting.value = true
  errorMessage.value = ''
  try {
    const created = await $fetch<{ id: string }>(`${config.public.apiBaseUrl}/study-spaces`, {
      method: 'POST',
      body: {
        tenant_id: '00000000-0000-0000-0000-000000000001',
        owner_user_id: '00000000-0000-0000-0000-000000000002',
        ...form
      }
    })
    await router.push(`/spaces/${created.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '创建学习空间失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section>
    <div class="topbar">
      <div>
        <h1>新建学习空间</h1>
        <p>填写目标，预览学习路线，然后创建空间。</p>
      </div>
    </div>

    <form class="card" style="display: grid; gap: 16px;" @submit.prevent="createSpace">
      <label>
        空间名称
        <input v-model="form.name" required maxlength="160" style="display: block; width: 100%; margin-top: 6px;" />
      </label>
      <label>
        学习目标
        <textarea v-model="form.goal" required rows="5" style="display: block; width: 100%; margin-top: 6px;" />
      </label>
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
        <label>
          基础水平
          <select v-model="form.level" style="display: block; width: 100%; margin-top: 6px;">
            <option value="beginner">入门</option>
            <option value="intermediate">有基础</option>
            <option value="advanced">进阶</option>
          </select>
        </label>
        <label>
          学习强度
          <select v-model="form.intensity" style="display: block; width: 100%; margin-top: 6px;">
            <option value="light">轻量</option>
            <option value="normal">标准</option>
            <option value="intensive">强化</option>
          </select>
        </label>
        <label>
          目标天数
          <input v-model.number="form.target_days" type="number" min="1" max="365" style="display: block; width: 100%; margin-top: 6px;" />
        </label>
      </div>

      <div>
        <button type="button" @click="renderDraftRoute">AI 渲染</button>
      </div>

      <div v-if="routeOutline.length" class="card">
        <h2>路线预览</h2>
        <ol>
          <li v-for="chapter in routeOutline" :key="chapter.order">
            <strong>{{ chapter.title }}</strong>
            <p>{{ chapter.description }}</p>
            <small>{{ chapter.estimated_days }} 天</small>
          </li>
        </ol>
      </div>

      <p v-if="errorMessage" style="color: #dc2626;">{{ errorMessage }}</p>
      <button class="primary-button" type="submit" :disabled="submitting">
        {{ submitting ? '创建中...' : '创建空间' }}
      </button>
    </form>
  </section>
</template>
```

- [ ] **Step 2: Add study space placeholder page**

Create `apps/web/pages/spaces/[id]/index.vue`:

```vue
<script setup lang="ts">
const route = useRoute()
</script>

<template>
  <section>
    <div class="topbar">
      <div>
        <h1>学习空间</h1>
        <p>空间 ID：{{ route.params.id }}</p>
      </div>
    </div>
    <div class="card">
      <h2>学习路线</h2>
      <p>下一阶段计划会在这里接入章节、资料库、RAG 和会话学习页。</p>
    </div>
  </section>
</template>
```

- [ ] **Step 3: Add component-level test**

Modify `apps/web/package.json` dev dependencies:

```json
"@vue/test-utils": "^2.4.0",
"happy-dom": "^15.11.0"
```

Create `apps/web/tests/create-space.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import NewSpacePage from '../pages/spaces/new.vue'

describe('NewSpacePage', () => {
  it('renders the AI render button and submit button', () => {
    const wrapper = mount(NewSpacePage, {
      global: {
        stubs: {
          NuxtLink: true
        }
      }
    })

    expect(wrapper.text()).toContain('AI 渲染')
    expect(wrapper.text()).toContain('创建空间')
  })
})
```

- [ ] **Step 4: Run front-end tests**

Run:

```bash
cd apps/web && npm install && npm run test
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add apps/web/pages/spaces apps/web/tests/create-space.spec.ts apps/web/package.json
git commit -m "feat(web): add study space creation flow"
```

---

### Task 8: End-to-End Foundation Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update project README**

Replace `README.md` with:

```markdown
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

RAG, LangGraph agents, streaming chat, quizzes, mastery tracking, and import/export are planned as separate implementation phases.

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
```

- [ ] **Step 2: Run backend verification**

Run:

```bash
cd apps/api && uv run pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
cd apps/web && npm run typecheck && npm run test
```

Expected: typecheck exits 0 and tests pass.

- [ ] **Step 4: Run compose config verification**

Run:

```bash
docker compose -f infra/docker-compose.yml config
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document foundation development workflow"
```

---

## Handoff Notes

After this plan is complete, write the next plan for RAG foundation:

- `source_chunks` table and migration.
- ingestion job table.
- text extraction adapter.
- chunking service.
- embedding provider abstraction.
- hybrid retrieval service.
- citation object model.
- tests for tenant/space/chapter retrieval isolation.

Do not implement LangGraph chat before the RAG foundation is tested. The session tutor depends on scoped retrieval and citation assembly.

## Self-Review

Spec coverage in this plan:

- Covered: foundation scaffold, database, tenant-aware study spaces, upload metadata, Nuxt shell, dashboard, create-space UI, deployment prerequisites.
- Not covered by design: RAG implementation, LangGraph agents, chat streaming, quizzes, mastery, review cards, import/export, observability dashboards, production auth. These are intentionally separate plans because each subsystem is independently testable.

Placeholder scan:

- No banned placeholder markers from the plan-writing checklist.
- Every implementation task names exact files and verification commands.

Type consistency:

- Study space fields are consistent across SQLAlchemy model, Pydantic schemas, API route, and Nuxt form: `tenant_id`, `owner_user_id`, `name`, `goal`, `level`, `intensity`, `target_days`.
- Source upload fields are consistent across schema and service: `tenant_id`, `study_space_id`, `filename`, `content_type`.
