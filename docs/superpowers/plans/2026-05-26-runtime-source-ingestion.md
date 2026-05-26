# Runtime Source Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make uploaded text and Markdown sources ingestible at runtime through authenticated APIs, backed by S3/MinIO object reads and source library endpoints.

**Architecture:** Extend the existing FastAPI modular monolith. Authenticated tenant context from the previous plan becomes the only tenant source for upload, source, and ingestion APIs. Storage remains behind `TextSourceReader`; this plan adds an S3-compatible implementation for text/Markdown objects and wires it into runtime ingestion. RAG retrieval and route generation remain separate concerns.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.x async, boto3, existing S3/MinIO settings, existing RAG ingestion/chunking/embedding services, pytest, httpx ASGI tests.

---

## Scope Check

This plan depends on PR #3, `codex/auth-tenant-context`, being merged first. PR #3 adds `CurrentUserContext`, membership-backed tenant authorization, and protected RAG retrieval. This plan assumes those dependencies exist.

In scope:

- S3/MinIO text object reader for `text/plain` and `text/markdown`.
- Upload presign API changed to derive tenant from `CurrentUserContext`.
- Source ownership checks against authorized tenant context.
- Source uploaded status transition API.
- Runtime ingestion route that uses S3 text reader instead of returning `501`.
- Source list/detail and chunk preview APIs for the Library surface.
- Tests for tenant isolation, source status, runtime ingestion wiring, and source chunk exposure.

Out of scope:

- Browser upload UX.
- OCR and PDF parsing.
- Webpage crawling.
- Background worker queue.
- AI route generation.
- LangGraph agents.
- Production JWT/session login.

## File Structure

Create or modify these files after PR #3 is merged into `main`:

```text
apps/api/
  app/
    api/
      router.py
      routes_ingestion.py
      routes_sources.py
      routes_uploads.py
    core/
      config.py
    domain/
      sources/
        schemas.py
        service.py
    infrastructure/
      storage.py
  tests/
    test_storage_reader.py
    test_uploads_auth.py
    test_sources_routes.py
    test_runtime_ingestion_route.py
README.md
apps/api/README.md
```

Responsibilities:

- `app/infrastructure/storage.py`: S3-compatible text reader and existing presign helper.
- `app/domain/sources/service.py`: tenant-safe source validation, listing, uploaded transition, chunk listing.
- `app/domain/sources/schemas.py`: API payloads/responses for presign, upload completion, sources, chunks.
- `app/api/routes_uploads.py`: authenticated presign endpoint deriving tenant from context.
- `app/api/routes_sources.py`: library/source status and chunk endpoints.
- `app/api/routes_ingestion.py`: authenticated runtime ingestion using S3 text reader.

---

### Task 1: Add S3 Text Source Reader

**Files:**
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/app/infrastructure/storage.py`
- Test: `apps/api/tests/test_storage_reader.py`

- [ ] **Step 1: Write failing storage reader tests**

Create `apps/api/tests/test_storage_reader.py`:

```python
import pytest

from app.infrastructure.storage import S3TextSourceReader


class FakeBody:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload


class FakeS3Client:
    def __init__(self, payload: bytes, content_type: str = "text/plain") -> None:
        self.payload = payload
        self.content_type = content_type
        self.calls = []

    def get_object(self, Bucket: str, Key: str):
        self.calls.append({"Bucket": Bucket, "Key": Key})
        return {
            "Body": FakeBody(self.payload),
            "ContentType": self.content_type,
            "ContentLength": len(self.payload),
        }


@pytest.mark.anyio
async def test_s3_text_source_reader_reads_utf8_text() -> None:
    client = FakeS3Client("hello learning".encode("utf-8"), content_type="text/markdown")
    reader = S3TextSourceReader(client=client, bucket="study-agent-local", max_bytes=1024)

    text = await reader.read_text("objects/intro.md")

    assert text == "hello learning"
    assert client.calls == [{"Bucket": "study-agent-local", "Key": "objects/intro.md"}]


@pytest.mark.anyio
async def test_s3_text_source_reader_rejects_large_object() -> None:
    client = FakeS3Client(b"abcdef", content_type="text/plain")
    reader = S3TextSourceReader(client=client, bucket="study-agent-local", max_bytes=3)

    with pytest.raises(ValueError) as exc_info:
        await reader.read_text("objects/too-large.txt")

    assert str(exc_info.value) == "Source object exceeds maximum text ingestion size"


@pytest.mark.anyio
async def test_s3_text_source_reader_rejects_binary_content_type() -> None:
    client = FakeS3Client(b"%PDF", content_type="application/pdf")
    reader = S3TextSourceReader(client=client, bucket="study-agent-local", max_bytes=1024)

    with pytest.raises(ValueError) as exc_info:
        await reader.read_text("objects/file.pdf")

    assert str(exc_info.value) == "Runtime text ingestion supports only text sources"
```

- [ ] **Step 2: Run test to verify it fails**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_storage_reader.py -q
```

Expected: FAIL because `S3TextSourceReader` does not exist.

- [ ] **Step 3: Add storage size setting**

Modify `apps/api/app/core/config.py`:

```python
    storage_text_max_bytes: int = 2_000_000
```

- [ ] **Step 4: Implement S3 text reader**

Modify `apps/api/app/infrastructure/storage.py`:

```python
import asyncio
from typing import Protocol

import boto3

from app.core.config import get_settings


TEXT_CONTENT_TYPES = {"text/plain", "text/markdown"}


class S3ClientProtocol(Protocol):
    def get_object(self, Bucket: str, Key: str):
        ...


class S3TextSourceReader(TextSourceReader):
    def __init__(self, client: S3ClientProtocol, bucket: str, max_bytes: int) -> None:
        self._client = client
        self._bucket = bucket
        self._max_bytes = max_bytes

    async def read_text(self, object_key: str) -> str:
        return await asyncio.to_thread(self._read_text_sync, object_key)

    def _read_text_sync(self, object_key: str) -> str:
        response = self._client.get_object(Bucket=self._bucket, Key=object_key)
        content_type = response.get("ContentType", "").split(";")[0].strip().lower()
        if content_type not in TEXT_CONTENT_TYPES:
            raise ValueError("Runtime text ingestion supports only text sources")
        content_length = int(response.get("ContentLength") or 0)
        if content_length > self._max_bytes:
            raise ValueError("Source object exceeds maximum text ingestion size")
        payload = response["Body"].read()
        if len(payload) > self._max_bytes:
            raise ValueError("Source object exceeds maximum text ingestion size")
        return payload.decode("utf-8")


def create_runtime_text_source_reader() -> S3TextSourceReader:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )
    return S3TextSourceReader(
        client=client,
        bucket=settings.s3_bucket,
        max_bytes=settings.storage_text_max_bytes,
    )
```

Keep existing `TextSourceReader` and `create_presigned_put_url` behavior.

- [ ] **Step 5: Run tests**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_storage_reader.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/core/config.py apps/api/app/infrastructure/storage.py apps/api/tests/test_storage_reader.py
git commit -m "feat: add s3 text source reader"
```

---

### Task 2: Make Upload Presign Tenant-Safe

**Files:**
- Modify: `apps/api/app/domain/sources/schemas.py`
- Modify: `apps/api/app/domain/sources/service.py`
- Modify: `apps/api/app/api/routes_uploads.py`
- Test: `apps/api/tests/test_uploads_auth.py`
- Modify: `apps/api/tests/test_uploads.py`

- [ ] **Step 1: Write route behavior tests**

Create `apps/api/tests/test_uploads_auth.py`:

```python
import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient

from app.api import routes_uploads
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


async def test_presign_upload_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)

    async def fake_create_upload_request(session, payload, tenant_id):
        captured["session"] = session
        captured["payload"] = payload
        captured["tenant_id"] = tenant_id

        class Source:
            id = uuid.UUID("00000000-0000-0000-0000-000000000010")
            object_key = "tenants/t/spaces/s/sources/source/intro.md"

        return Source(), "http://upload.local"

    monkeypatch.setattr(routes_uploads, "create_upload_request", fake_create_upload_request)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/uploads/presign",
                json={
                    "study_space_id": str(study_space_id),
                    "filename": "intro.md",
                    "content_type": "text/markdown",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["tenant_id"] == tenant_id
    assert captured["payload"].study_space_id == study_space_id
    assert not hasattr(captured["payload"], "tenant_id")


async def test_presign_upload_rejects_client_tenant_id() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/uploads/presign",
            headers={
                "X-User-Id": str(uuid.uuid4()),
                "X-Tenant-Id": str(uuid.uuid4()),
            },
            json={
                "tenant_id": str(uuid.uuid4()),
                "study_space_id": str(uuid.uuid4()),
                "filename": "intro.md",
                "content_type": "text/markdown",
            },
        )

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_uploads_auth.py -q
```

Expected: FAIL because upload schema still accepts/requires `tenant_id` and route has no auth context dependency.

- [ ] **Step 3: Modify upload schema**

Modify `apps/api/app/domain/sources/schemas.py`:

```python
from pydantic import BaseModel, ConfigDict, Field


class UploadPresignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_space_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
```

Remove `tenant_id` from the request model.

- [ ] **Step 4: Add tenant study-space verification**

Modify `apps/api/app/domain/sources/service.py`:

```python
from sqlalchemy import select

from app.db.models import Source, StudySpace


async def ensure_study_space_in_tenant(
    session: AsyncSession,
    study_space_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> StudySpace:
    study_space = await session.scalar(
        select(StudySpace).where(
            StudySpace.id == study_space_id,
            StudySpace.tenant_id == tenant_id,
        )
    )
    if study_space is None:
        raise ValueError("Study space not found for tenant")
    return study_space
```

Change `create_upload_request` signature:

```python
async def create_upload_request(
    session: AsyncSession,
    payload: UploadPresignRequest,
    tenant_id: uuid.UUID,
) -> tuple[Source, str]:
    validate_content_type(payload.content_type)
    await ensure_study_space_in_tenant(
        session=session,
        study_space_id=payload.study_space_id,
        tenant_id=tenant_id,
    )
    object_key = build_object_key(tenant_id, payload.study_space_id, payload.filename)
    source = Source(
        tenant_id=tenant_id,
        study_space_id=payload.study_space_id,
        filename=payload.filename,
        content_type=payload.content_type,
        object_key=object_key,
    )
    ...
```

- [ ] **Step 5: Protect upload route**

Modify `apps/api/app/api/routes_uploads.py`:

```python
from app.core.auth import CurrentUserContext, get_authorized_user_context


@router.post("/presign", response_model=UploadPresignResponse)
async def presign_upload(
    payload: UploadPresignRequest,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> UploadPresignResponse:
    try:
        source, upload_url = await create_upload_request(
            session=session,
            payload=payload,
            tenant_id=context.tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadPresignResponse(...)
```

- [ ] **Step 6: Update existing unit tests**

Modify `apps/api/tests/test_uploads.py` so request construction no longer passes `tenant_id`; call `create_upload_request` with explicit `tenant_id` and a fake or monkeypatched `ensure_study_space_in_tenant` if needed.

Use this test shape:

```python
async def test_create_upload_request_uses_tenant_context(monkeypatch, fake_session) -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()

    async def fake_ensure_study_space_in_tenant(session, study_space_id, tenant_id):
        return object()

    monkeypatch.setattr(
        "app.domain.sources.service.ensure_study_space_in_tenant",
        fake_ensure_study_space_in_tenant,
    )
    payload = UploadPresignRequest(
        study_space_id=study_space_id,
        filename="intro.md",
        content_type="text/markdown",
    )
    source, upload_url = await create_upload_request(
        session=fake_session,
        payload=payload,
        tenant_id=tenant_id,
    )

    assert source.tenant_id == tenant_id
```

Adapt to the existing fixture style in `tests/test_uploads.py`.

- [ ] **Step 7: Run tests**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_uploads.py tests/test_uploads_auth.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add apps/api/app/domain/sources/schemas.py apps/api/app/domain/sources/service.py apps/api/app/api/routes_uploads.py apps/api/tests/test_uploads.py apps/api/tests/test_uploads_auth.py
git commit -m "feat: protect upload presign with tenant context"
```

---

### Task 3: Add Source Library Service and Routes

**Files:**
- Modify: `apps/api/app/domain/sources/schemas.py`
- Modify: `apps/api/app/domain/sources/service.py`
- Create: `apps/api/app/api/routes_sources.py`
- Modify: `apps/api/app/api/router.py`
- Test: `apps/api/tests/test_sources_routes.py`

- [ ] **Step 1: Write route tests**

Create `apps/api/tests/test_sources_routes.py`:

```python
import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient

from app.api import routes_sources
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


async def test_list_sources_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_list_sources_for_space(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(routes_sources, "list_sources_for_space", fake_list_sources_for_space)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/study-spaces/{study_space_id}/sources")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"sources": []}
    assert captured["tenant_id"] == tenant_id
    assert captured["study_space_id"] == study_space_id


async def test_mark_source_uploaded_maps_missing_source_to_404(monkeypatch) -> None:
    source_id = uuid.uuid4()

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_mark_source_uploaded(**kwargs):
        raise ValueError("Source not found for tenant")

    monkeypatch.setattr(routes_sources, "mark_source_uploaded", fake_mark_source_uploaded)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/sources/{source_id}/uploaded")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Source not found for tenant"}
```

- [ ] **Step 2: Run route tests to verify failure**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_sources_routes.py -q
```

Expected: FAIL because `routes_sources` does not exist.

- [ ] **Step 3: Add source schemas**

Modify `apps/api/app/domain/sources/schemas.py`:

```python
from datetime import datetime


class SourceResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    filename: str
    content_type: str
    object_key: str
    status: str
    error_message: str | None
    created_at: datetime | None = None


class SourceListResponse(BaseModel):
    sources: list[SourceResponse]


class SourceUploadedResponse(BaseModel):
    source: SourceResponse


class SourceChunkResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    chunk_index: int
    text: str
    citation: dict


class SourceChunkListResponse(BaseModel):
    chunks: list[SourceChunkResponse]
```

- [ ] **Step 4: Add source service functions**

Modify `apps/api/app/domain/sources/service.py`:

```python
from sqlalchemy import select

from app.db.models import Source, SourceChunk, SourceStatus


async def get_source_for_tenant(
    session: AsyncSession,
    source_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Source:
    source = await session.scalar(
        select(Source).where(Source.id == source_id, Source.tenant_id == tenant_id)
    )
    if source is None:
        raise ValueError("Source not found for tenant")
    return source


async def list_sources_for_space(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> list[Source]:
    await ensure_study_space_in_tenant(
        session=session,
        study_space_id=study_space_id,
        tenant_id=tenant_id,
    )
    rows = await session.scalars(
        select(Source)
        .where(Source.tenant_id == tenant_id, Source.study_space_id == study_space_id)
        .order_by(Source.created_at.desc(), Source.id)
    )
    return list(rows)


async def mark_source_uploaded(
    session: AsyncSession,
    source_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Source:
    source = await get_source_for_tenant(session=session, source_id=source_id, tenant_id=tenant_id)
    if source.status != SourceStatus.pending_upload:
        raise ValueError(f"Source cannot be marked uploaded from status {source.status.value}")
    source.status = SourceStatus.uploaded
    await session.commit()
    await session.refresh(source)
    return source


async def list_source_chunks(
    session: AsyncSession,
    source_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[SourceChunk]:
    await get_source_for_tenant(session=session, source_id=source_id, tenant_id=tenant_id)
    rows = await session.scalars(
        select(SourceChunk)
        .where(SourceChunk.source_id == source_id, SourceChunk.tenant_id == tenant_id)
        .order_by(SourceChunk.chunk_index)
    )
    return list(rows)
```

- [ ] **Step 5: Add source routes**

Create `apps/api/app/api/routes_sources.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.sources.schemas import (
    SourceChunkListResponse,
    SourceChunkResponse,
    SourceListResponse,
    SourceResponse,
    SourceUploadedResponse,
)
from app.domain.sources.service import list_source_chunks, list_sources_for_space, mark_source_uploaded

router = APIRouter(tags=["sources"])


def to_source_response(source) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        tenant_id=source.tenant_id,
        study_space_id=source.study_space_id,
        filename=source.filename,
        content_type=source.content_type,
        object_key=source.object_key,
        status=source.status.value,
        error_message=source.error_message,
        created_at=source.created_at,
    )


@router.get("/study-spaces/{study_space_id}/sources", response_model=SourceListResponse)
async def list_sources(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> SourceListResponse:
    try:
        sources = await list_sources_for_space(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SourceListResponse(sources=[to_source_response(source) for source in sources])


@router.post("/sources/{source_id}/uploaded", response_model=SourceUploadedResponse)
async def complete_source_upload(
    source_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> SourceUploadedResponse:
    try:
        source = await mark_source_uploaded(
            session=session,
            source_id=source_id,
            tenant_id=context.tenant_id,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Source not found for tenant" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SourceUploadedResponse(source=to_source_response(source))


@router.get("/sources/{source_id}/chunks", response_model=SourceChunkListResponse)
async def get_source_chunks(
    source_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> SourceChunkListResponse:
    try:
        chunks = await list_source_chunks(
            session=session,
            source_id=source_id,
            tenant_id=context.tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SourceChunkListResponse(
        chunks=[
            SourceChunkResponse(
                id=chunk.id,
                source_id=chunk.source_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                citation=chunk.citation,
            )
            for chunk in chunks
        ]
    )
```

- [ ] **Step 6: Register routes**

Modify `apps/api/app/api/router.py`:

```python
from app.api import routes_health, routes_ingestion, routes_retrieval, routes_sources, routes_study_spaces, routes_uploads

api_router.include_router(routes_sources.router)
```

Keep existing route registrations.

- [ ] **Step 7: Run tests**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_sources_routes.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add apps/api/app/domain/sources/schemas.py apps/api/app/domain/sources/service.py apps/api/app/api/routes_sources.py apps/api/app/api/router.py apps/api/tests/test_sources_routes.py
git commit -m "feat: add source library api"
```

---

### Task 4: Enforce Tenant Ownership in Ingestion

**Files:**
- Modify: `apps/api/app/domain/rag/ingestion.py`
- Test: `apps/api/tests/test_rag_ingestion.py`

- [ ] **Step 1: Add ingestion tenant validation tests**

Append to `apps/api/tests/test_rag_ingestion.py`:

```python
import uuid

import pytest

from app.db.models import Source, SourceStatus
from app.domain.rag.ingestion import validate_source_for_ingestion


def test_validate_source_for_ingestion_rejects_wrong_tenant() -> None:
    source = Source(
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        filename="intro.md",
        content_type="text/markdown",
        object_key="objects/intro.md",
        status=SourceStatus.uploaded,
    )

    with pytest.raises(ValueError) as exc_info:
        validate_source_for_ingestion(source=source, tenant_id=uuid.uuid4())

    assert str(exc_info.value) == "Source not found for tenant"
```

- [ ] **Step 2: Run test to verify failure**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_rag_ingestion.py -q
```

Expected: FAIL because `validate_source_for_ingestion` does not exist.

- [ ] **Step 3: Add validation helper and tenant parameter**

Modify `apps/api/app/domain/rag/ingestion.py`:

```python
def validate_source_for_ingestion(source: Source, tenant_id: uuid.UUID | None) -> None:
    if tenant_id is not None and source.tenant_id != tenant_id:
        raise ValueError("Source not found for tenant")
```

Change `ingest_source` signature:

```python
async def ingest_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    reader: TextSourceReader,
    embedding_provider: EmbeddingProvider,
    max_chars: int,
    overlap_chars: int,
    tenant_id: uuid.UUID | None = None,
) -> IngestionResult:
```

After loading source and before status validation:

```python
validate_source_for_ingestion(source=source, tenant_id=tenant_id)
```

In any atomic claim query/update, include the tenant predicate only when `tenant_id` is present:

```python
claim_conditions = [Source.id == source_id, Source.status == SourceStatus.uploaded]
if tenant_id is not None:
    claim_conditions.append(Source.tenant_id == tenant_id)

claim_result = await session.execute(
    update(Source)
    .where(*claim_conditions)
    .values(status=SourceStatus.processing)
)
```

Keep existing source-not-found and status validation behavior for test callers that do not pass a tenant.

- [ ] **Step 4: Run tests**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_rag_ingestion.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/rag/ingestion.py apps/api/tests/test_rag_ingestion.py
git commit -m "feat: enforce tenant ownership during ingestion"
```

---

### Task 5: Wire Runtime Ingestion Route to S3 Reader

**Files:**
- Modify: `apps/api/app/api/routes_ingestion.py`
- Test: `apps/api/tests/test_runtime_ingestion_route.py`

- [ ] **Step 1: Write runtime ingestion route tests**

Create `apps/api/tests/test_runtime_ingestion_route.py`:

```python
import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_ingestion
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


async def test_ingestion_route_uses_runtime_text_reader(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    captured = {}

    class FakeReader:
        pass

    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    def fake_create_runtime_text_source_reader() -> FakeReader:
        return FakeReader()

    async def fake_ingest_source(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            job_id=uuid.UUID("00000000-0000-0000-0000-000000000020"),
            source_id=source_id,
            status="completed",
            chunk_count=2,
        )

    monkeypatch.setattr(
        routes_ingestion,
        "create_runtime_text_source_reader",
        fake_create_runtime_text_source_reader,
    )
    monkeypatch.setattr(routes_ingestion, "ingest_source", fake_ingest_source)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/ingestion/sources/{source_id}/run")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert captured["source_id"] == source_id
    assert captured["tenant_id"] == tenant_id
    assert isinstance(captured["reader"], FakeReader)


async def test_ingestion_route_maps_source_errors_to_400(monkeypatch) -> None:
    async def fake_get_db_session() -> AsyncGenerator[object, None]:
        yield object()

    async def fake_get_authorized_user_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    def fake_create_runtime_text_source_reader():
        return object()

    async def fake_ingest_source(**kwargs):
        raise ValueError("Source must be uploaded before ingestion, got pending_upload")

    monkeypatch.setattr(routes_ingestion, "create_runtime_text_source_reader", fake_create_runtime_text_source_reader)
    monkeypatch.setattr(routes_ingestion, "ingest_source", fake_ingest_source)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_get_authorized_user_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/ingestion/sources/{uuid.uuid4()}/run")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Source must be uploaded before ingestion, got pending_upload"
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_runtime_ingestion_route.py -q
```

Expected: FAIL because the route still returns `501` before calling ingestion.

- [ ] **Step 3: Implement runtime ingestion route**

Modify `apps/api/app/api/routes_ingestion.py`:

```python
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.infrastructure.storage import create_runtime_text_source_reader


@router.post("/sources/{source_id}/run", response_model=IngestSourceResponse)
async def run_source_ingestion(
    source_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> IngestSourceResponse:
    settings = get_settings()
    try:
        result = await ingest_source(
            session=session,
            source_id=source_id,
            reader=create_runtime_text_source_reader(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=settings.rag_embedding_dimension),
            max_chars=settings.rag_chunk_max_chars,
            overlap_chars=settings.rag_chunk_overlap_chars,
            tenant_id=context.tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IngestSourceResponse(
        job_id=result.job_id,
        source_id=result.source_id,
        status=result.status,
        chunk_count=result.chunk_count,
    )
```

`context.tenant_id` is passed into the domain service so the route never ingests a source outside the authenticated tenant.

- [ ] **Step 4: Run tests**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest tests/test_runtime_ingestion_route.py tests/test_ingestion_routes.py -q
```

Expected: PASS. Update `tests/test_ingestion_routes.py` if it still expects ingestion `501`.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/api/routes_ingestion.py apps/api/tests/test_runtime_ingestion_route.py apps/api/tests/test_ingestion_routes.py
git commit -m "feat: enable runtime text ingestion route"
```

---

### Task 6: Documentation and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `apps/api/README.md`

- [ ] **Step 1: Update docs**

Modify `README.md` RAG section:

```markdown
Runtime ingestion supports text and Markdown objects in S3-compatible storage after a source is marked uploaded. PDF, OCR, and webpage ingestion remain later phases.
```

Modify `apps/api/README.md`:

```markdown
## Runtime source ingestion

Local text/Markdown ingestion flow:

1. `POST /api/v1/uploads/presign` with development auth headers.
2. Upload the object to the returned URL.
3. `POST /api/v1/sources/{source_id}/uploaded`.
4. `POST /api/v1/ingestion/sources/{source_id}/run`.
5. Inspect chunks with `GET /api/v1/sources/{source_id}/chunks`.

Runtime ingestion currently supports `text/plain` and `text/markdown` objects. PDF, OCR, images, and webpage ingestion are intentionally out of scope for this phase.
```

- [ ] **Step 2: Run API tests**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest -q
```

Expected: all non-guarded tests PASS; guarded Postgres tests may be skipped.

- [ ] **Step 3: Run lint**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m ruff check .
```

Expected: PASS.

- [ ] **Step 4: Validate Docker Compose**

Run from repo root:

```powershell
docker compose -f infra/docker-compose.yml config
```

Expected: exit code 0. Docker credential warnings can be recorded as environmental if config prints successfully.

- [ ] **Step 5: Commit docs**

```powershell
git add README.md apps/api/README.md
git commit -m "docs: describe runtime source ingestion"
```

## Final Verification

Before creating a PR, run:

```powershell
cd apps/api
$env:PYTHONPATH = "$PWD"
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m pytest -q
& "F:\AIproject\study_agent\.worktrees\codex-rag-foundation\apps\api\.venv\Scripts\python.exe" -m ruff check .
cd ..\..
docker compose -f infra/docker-compose.yml config
```

Record:

- API test count and skipped guarded integration tests.
- Ruff result.
- Docker Compose result and any environment-only warning.

## Execution Order

1. Merge PR #3 into `main`.
2. Create branch `codex/runtime-source-ingestion`.
3. Execute Tasks 1-6 in order.
4. Push branch and open PR.
5. Preserve the worktree until PR feedback is resolved.

## Self-Review

- Spec coverage: This plan makes runtime source ingestion real for text/Markdown while preserving tenant isolation and auth context boundaries.
- Incomplete-content scan: No incomplete markers are required for execution. PDF/OCR/web ingestion are explicitly out of scope.
- Type consistency: `TextSourceReader`, `S3TextSourceReader`, `UploadPresignRequest`, `SourceResponse`, and `IngestionResult` are used consistently across service, route, and test tasks.
- Scope control: This is a backend runtime ingestion and library API plan. Frontend upload UX and AI route generation are intentionally deferred to keep the PR reviewable.
