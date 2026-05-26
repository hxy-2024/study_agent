# Auth Tenant Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal production-shaped authentication and tenant context foundation so protected APIs, especially RAG retrieval, no longer trust caller-supplied tenant IDs.

**Architecture:** Build a lightweight auth boundary inside `apps/api` using explicit FastAPI dependencies. For this phase, authentication is development-header based and membership-backed: requests provide user and tenant IDs through headers, the API verifies that the user belongs to the tenant, then downstream routes consume `CurrentUserContext`. This intentionally avoids full password login, JWT issuance, SSO, or frontend session UI; those are later plans.

**Tech Stack:** FastAPI dependencies, Pydantic v2, SQLAlchemy 2.x async, existing `users`, `tenants`, and `memberships` tables, pytest, httpx ASGI tests.

---

## Scope Check

This plan depends on PR #2, `codex/rag-foundation`, being merged first. PR #2 intentionally leaves `POST /api/v1/rag/retrieve` guarded behind `501` because returning private source chunks based on a request-body `tenant_id` is unsafe.

This plan implements only the API-side tenant context needed to safely unlock RAG retrieval and provide a reusable boundary for later features.

In scope:

- Development-header authentication dependency.
- Membership-backed tenant authorization.
- Reusable `CurrentUserContext` model.
- Protected RAG retrieval route that derives tenant from auth context.
- Tests for missing auth, invalid UUID headers, missing membership, and successful retrieval.
- Documentation for local development headers.

Out of scope:

- Password login.
- JWT token minting.
- OAuth/SSO.
- Frontend sign-in UI.
- Organization admin UI.
- Full RBAC policy matrix.
- Audit log search UI.

## File Structure

Create or modify these files after PR #2 is merged into `main`:

```text
apps/api/
  app/
    api/
      routes_retrieval.py
    core/
      auth.py
      config.py
    domain/
      rag/
        schemas.py
  tests/
    test_auth_context.py
    test_retrieval_auth_routes.py
README.md
apps/api/README.md
```

Responsibilities:

- `app/core/auth.py`: FastAPI dependencies and `CurrentUserContext`.
- `app/core/config.py`: development auth toggle.
- `app/domain/rag/schemas.py`: split client retrieval request from internal tenant-scoped retrieval.
- `app/api/routes_retrieval.py`: enforce auth context before returning chunks.
- `tests/test_auth_context.py`: dependency-level auth and membership tests.
- `tests/test_retrieval_auth_routes.py`: HTTP route behavior tests.

---

### Task 1: Add Development Auth Settings

**Files:**
- Modify: `apps/api/app/core/config.py`
- Test: `apps/api/tests/test_auth_context.py`

- [ ] **Step 1: Write the failing settings test**

Create `apps/api/tests/test_auth_context.py`:

```python
from app.core.config import Settings


def test_dev_auth_settings_default_to_enabled_for_local_foundation() -> None:
    settings = Settings()

    assert settings.dev_auth_enabled is True
    assert settings.auth_user_header == "X-User-Id"
    assert settings.auth_tenant_header == "X-Tenant-Id"
```

- [ ] **Step 2: Run the test to verify it fails**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_auth_context.py -q
```

Expected: FAIL because the settings do not exist.

- [ ] **Step 3: Add settings**

Modify `apps/api/app/core/config.py`:

```python
    dev_auth_enabled: bool = True
    auth_user_header: str = "X-User-Id"
    auth_tenant_header: str = "X-Tenant-Id"
```

Keep the fields inside the existing `Settings` class and do not change existing settings.

- [ ] **Step 4: Run the test**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_auth_context.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/core/config.py apps/api/tests/test_auth_context.py
git commit -m "test: define dev auth settings"
```

---

### Task 2: Implement Current User Context Dependency

**Files:**
- Create: `apps/api/app/core/auth.py`
- Modify: `apps/api/tests/test_auth_context.py`

- [ ] **Step 1: Extend auth dependency tests**

Append to `apps/api/tests/test_auth_context.py`:

```python
import uuid

import pytest
from fastapi import HTTPException

from app.core.auth import CurrentUserContext, parse_dev_auth_headers


def test_parse_dev_auth_headers_returns_context() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    context = parse_dev_auth_headers(
        user_id_header=str(user_id),
        tenant_id_header=str(tenant_id),
    )

    assert context == CurrentUserContext(user_id=user_id, tenant_id=tenant_id)


def test_parse_dev_auth_headers_requires_both_headers() -> None:
    with pytest.raises(HTTPException) as exc_info:
        parse_dev_auth_headers(user_id_header=None, tenant_id_header=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing development auth headers"


def test_parse_dev_auth_headers_rejects_invalid_uuid() -> None:
    with pytest.raises(HTTPException) as exc_info:
        parse_dev_auth_headers(user_id_header="not-a-uuid", tenant_id_header=str(uuid.uuid4()))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid development auth header UUID"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_auth_context.py -q
```

Expected: FAIL because `app.core.auth` does not exist.

- [ ] **Step 3: Implement auth context parsing**

Create `apps/api/app/core/auth.py`:

```python
import uuid
from dataclasses import dataclass

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class CurrentUserContext:
    user_id: uuid.UUID
    tenant_id: uuid.UUID


def parse_dev_auth_headers(
    user_id_header: str | None,
    tenant_id_header: str | None,
) -> CurrentUserContext:
    if not user_id_header or not tenant_id_header:
        raise HTTPException(status_code=401, detail="Missing development auth headers")
    try:
        user_id = uuid.UUID(user_id_header)
        tenant_id = uuid.UUID(tenant_id_header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid development auth header UUID") from exc
    return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)


async def get_current_user_context(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> CurrentUserContext:
    return parse_dev_auth_headers(user_id_header=x_user_id, tenant_id_header=x_tenant_id)
```

- [ ] **Step 4: Run tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_auth_context.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/core/auth.py apps/api/tests/test_auth_context.py
git commit -m "feat: add dev auth context parser"
```

---

### Task 3: Add Membership Authorization Dependency

**Files:**
- Modify: `apps/api/app/core/auth.py`
- Modify: `apps/api/tests/test_auth_context.py`

- [ ] **Step 1: Add membership dependency tests**

Append to `apps/api/tests/test_auth_context.py`:

```python
from app.core.auth import ensure_tenant_membership
from app.db.models import Membership


class FakeScalarSession:
    def __init__(self, result):
        self.result = result

    async def scalar(self, statement):
        self.statement = statement
        return self.result


@pytest.mark.anyio
async def test_ensure_tenant_membership_allows_existing_membership() -> None:
    context = CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())
    membership = Membership(tenant_id=context.tenant_id, user_id=context.user_id, role="owner")
    session = FakeScalarSession(result=membership)

    result = await ensure_tenant_membership(context=context, session=session)

    assert result == context


@pytest.mark.anyio
async def test_ensure_tenant_membership_rejects_missing_membership() -> None:
    context = CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())
    session = FakeScalarSession(result=None)

    with pytest.raises(HTTPException) as exc_info:
        await ensure_tenant_membership(context=context, session=session)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User is not a member of this tenant"
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_auth_context.py -q
```

Expected: FAIL because `ensure_tenant_membership` does not exist.

- [ ] **Step 3: Implement membership dependency**

Modify `apps/api/app/core/auth.py`:

```python
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Membership


class ScalarSession(Protocol):
    async def scalar(self, statement):
        ...


async def ensure_tenant_membership(
    context: CurrentUserContext,
    session: ScalarSession,
) -> CurrentUserContext:
    membership = await session.scalar(
        select(Membership).where(
            Membership.tenant_id == context.tenant_id,
            Membership.user_id == context.user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="User is not a member of this tenant")
    return context
```

Also add a route-ready dependency:

```python
from fastapi import Depends

from app.db.session import get_db_session


async def get_authorized_user_context(
    context: CurrentUserContext = Depends(get_current_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUserContext:
    return await ensure_tenant_membership(context=context, session=session)
```

Do not wire this route-ready dependency yet; Task 5 will wire it with FastAPI `Depends`.

- [ ] **Step 4: Run tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_auth_context.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/core/auth.py apps/api/tests/test_auth_context.py
git commit -m "feat: verify tenant membership"
```

---

### Task 4: Split Retrieval API Request From Tenant Scope

**Files:**
- Modify: `apps/api/app/domain/rag/schemas.py`
- Test: `apps/api/tests/test_rag_retrieval.py`

- [ ] **Step 1: Add schema test**

Append to `apps/api/tests/test_rag_retrieval.py`:

```python
from pydantic import ValidationError

from app.domain.rag.schemas import RetrieveRequest


def test_retrieve_request_does_not_accept_client_tenant_scope() -> None:
    payload = RetrieveRequest(query="matrix rank", limit=5)

    assert payload.query == "matrix rank"
    assert payload.limit == 5


def test_retrieve_request_rejects_empty_query() -> None:
    try:
        RetrieveRequest(query="", limit=5)
    except ValidationError:
        return
    raise AssertionError("Expected ValidationError")
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_rag_retrieval.py -q
```

Expected: FAIL because `RetrieveRequest` still requires `tenant_id` and `study_space_id`.

- [ ] **Step 3: Modify retrieval request schema**

Modify `apps/api/app/domain/rag/schemas.py`:

```python
class RetrieveRequest(BaseModel):
    study_space_id: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
```

Remove `tenant_id` from the request model. The route will derive tenant from `CurrentUserContext`.

- [ ] **Step 4: Update schema test payload**

Adjust `test_retrieve_request_does_not_accept_client_tenant_scope` so it includes `study_space_id`:

```python
def test_retrieve_request_does_not_accept_client_tenant_scope() -> None:
    payload = RetrieveRequest(study_space_id=uuid.uuid4(), query="matrix rank", limit=5)

    assert payload.query == "matrix rank"
    assert payload.limit == 5
    assert not hasattr(payload, "tenant_id")
```

Adjust the empty query test similarly:

```python
RetrieveRequest(study_space_id=uuid.uuid4(), query="", limit=5)
```

- [ ] **Step 5: Run tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_rag_retrieval.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/domain/rag/schemas.py apps/api/tests/test_rag_retrieval.py
git commit -m "feat: derive tenant scope outside retrieval payload"
```

---

### Task 5: Re-enable Protected RAG Retrieval Route

**Files:**
- Modify: `apps/api/app/api/routes_retrieval.py`
- Create: `apps/api/tests/test_retrieval_auth_routes.py`
- Modify: `apps/api/tests/test_ingestion_routes.py`

- [ ] **Step 1: Write protected route tests**

Create `apps/api/tests/test_retrieval_auth_routes.py`:

```python
import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient

from app.api import routes_retrieval
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


async def test_retrieval_route_requires_auth_context() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/rag/retrieve",
            json={"study_space_id": str(uuid.uuid4()), "query": "linear algebra", "limit": 5},
        )

    assert response.status_code == 401


async def test_retrieval_route_uses_authorized_tenant_context(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_retrieve_chunks(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(routes_retrieval, "retrieve_chunks", fake_retrieve_chunks)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/rag/retrieve",
                json={"study_space_id": str(study_space_id), "query": "linear algebra", "limit": 5},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"query": "linear algebra", "chunks": []}
    assert captured["tenant_id"] == tenant_id
    assert captured["study_space_id"] == study_space_id
    assert captured["query"] == "linear algebra"
    assert captured["limit"] == 5


async def test_retrieval_route_maps_domain_value_error_to_400(monkeypatch) -> None:
    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_retrieve_chunks(**kwargs):
        raise ValueError("Embedding dimension must be 16")

    monkeypatch.setattr(routes_retrieval, "retrieve_chunks", fake_retrieve_chunks)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/rag/retrieve",
                json={"study_space_id": str(uuid.uuid4()), "query": "linear algebra", "limit": 5},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "Embedding dimension must be 16"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_retrieval_auth_routes.py -q
```

Expected: FAIL because the route still returns `501`.

- [ ] **Step 3: Implement protected retrieval route**

Modify `apps/api/app/api/routes_retrieval.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.core.config import get_settings
from app.db.session import get_db_session
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.retrieval import retrieve_chunks
from app.domain.rag.schemas import RetrieveRequest, RetrievedChunkResponse, RetrieveResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_rag_chunks(
    payload: RetrieveRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> RetrieveResponse:
    settings = get_settings()
    embedding_provider = DeterministicEmbeddingProvider(settings.rag_embedding_dimension)
    try:
        chunks = await retrieve_chunks(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=payload.study_space_id,
            query=payload.query,
            limit=payload.limit,
            embedding_provider=embedding_provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RetrieveResponse(
        query=payload.query,
        chunks=[
            RetrievedChunkResponse(
                chunk_id=chunk.id,
                source_id=chunk.source_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                citation=chunk.citation,
                score=chunk.score,
            )
            for chunk in chunks
        ],
    )
```

- [ ] **Step 4: Update old route test**

Modify `apps/api/tests/test_ingestion_routes.py`:

- Keep `test_rag_routes_are_registered`.
- Keep ingestion `501` test.
- Remove the test that expects retrieval `501`, because retrieval is now protected and enabled.

- [ ] **Step 5: Run tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest tests/test_retrieval_auth_routes.py tests/test_ingestion_routes.py tests/test_rag_retrieval.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/api/routes_retrieval.py apps/api/tests/test_retrieval_auth_routes.py apps/api/tests/test_ingestion_routes.py
git commit -m "feat: protect rag retrieval with tenant context"
```

---

### Task 6: Document Local Auth Headers

**Files:**
- Modify: `README.md`
- Modify: `apps/api/README.md`

- [ ] **Step 1: Update root README**

Modify the RAG section in `README.md` so it no longer says runtime retrieval returns `501`. Use:

```markdown
Runtime ingestion returns `501` until object-storage text reading is configured. Runtime retrieval is enabled only when the request includes valid development auth headers and the user is a member of the tenant.
```

Add a local auth section:

```markdown
### Development auth headers

Local protected API calls use development headers until the full login flow is implemented:

- `X-User-Id`: existing user UUID
- `X-Tenant-Id`: existing tenant UUID

The API verifies membership before returning tenant-scoped data.
```

- [ ] **Step 2: Update API README**

Add to `apps/api/README.md`:

```markdown
## Development auth

Protected local endpoints use development headers:

```powershell
$headers = @{
  "X-User-Id" = "<user uuid>"
  "X-Tenant-Id" = "<tenant uuid>"
}
```

The headers are temporary. Production auth will replace them with a proper session/JWT provider while keeping the same `CurrentUserContext` boundary.
```

- [ ] **Step 3: Commit**

```powershell
git add README.md apps/api/README.md
git commit -m "docs: document development auth headers"
```

---

### Task 7: Final Verification

**Files:**
- No code files unless verification reveals a defect.

- [ ] **Step 1: Run API tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest -q
```

Expected: all non-guarded tests PASS. Guarded Postgres tests may be skipped unless `RUN_POSTGRES_TESTS=1`.

- [ ] **Step 2: Run lint**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run ruff check .
```

Expected: PASS.

- [ ] **Step 3: Validate Docker Compose**

Run from repo root:

```powershell
docker compose -f infra/docker-compose.yml config
```

Expected: exit code 0. Docker credential warnings can be recorded as environmental if the config prints successfully.

- [ ] **Step 4: Commit verification notes only if files changed**

If no files changed, do not create an empty commit.

## Final Verification

Before creating a PR, run:

```powershell
cd apps/api
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON = "C:\Users\you\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
uv run pytest -q
uv run ruff check .
cd ..\..
docker compose -f infra/docker-compose.yml config
```

Record:

- API test count and skipped guarded integration tests.
- Ruff result.
- Docker Compose result and any environment-only warning.

## Execution Order

1. Merge PR #2 into `main`.
2. Create branch `codex/auth-tenant-context`.
3. Execute Tasks 1-7 in order.
4. Push branch and open PR.
5. Do not delete the worktree until PR feedback is resolved.

## Self-Review

- Spec coverage: This plan unlocks safe runtime RAG retrieval by deriving tenant scope from verified membership instead of trusting request-body tenant IDs.
- Incomplete-content scan: No incomplete markers are required for execution. Full login/JWT is explicitly out of scope.
- Type consistency: `CurrentUserContext`, `RetrieveRequest`, and `get_authorized_user_context` are used consistently across tests and route code.
- Scope control: This plan deliberately avoids frontend auth UI and full RBAC so the next PR remains small and reviewable.
