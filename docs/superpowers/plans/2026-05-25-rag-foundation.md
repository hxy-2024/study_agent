# Study Agent RAG Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-shaped RAG foundation for study_agent: source ingestion jobs, text extraction, chunking, embedding provider abstraction, pgvector storage, scoped retrieval, and citation-ready API responses.

**Architecture:** Extend the existing Production Modular Monolith in `apps/api`. RAG remains a backend domain module with clear interfaces: ingestion reads uploaded source metadata, extraction converts source content to normalized text pages, chunking creates citation-bearing chunks, embeddings are generated through a provider abstraction, and retrieval is scoped by tenant and study space. This plan does not implement LangGraph agents, streaming chat, frontend study pages, OCR, PDF parsing, or reranking UI.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x async, Alembic, Postgres, pgvector, pytest, pytest-asyncio, deterministic test embeddings, S3-compatible storage abstraction.

---

## Scope Check

This plan depends on the foundation PR being merged first because it modifies `apps/api`, existing `Source` models, upload status behavior, and API routing. The first RAG increment must be independently useful and testable:

- A source can be marked uploaded.
- An ingestion job can be created and run synchronously from an API endpoint.
- Text and Markdown sources can be extracted from storage text content.
- Extracted content can be chunked into stable, citation-ready chunks.
- Chunks can be embedded through an interface.
- Chunks can be stored with vector metadata.
- Retrieval can return the most relevant chunks for one tenant and one study space.

Out of scope for this plan:

- PDF binary parsing.
- OCR for images.
- Webpage crawling.
- LangGraph workflow orchestration.
- SSE chat.
- Quiz generation.
- Production model provider credentials.
- Background worker queue.

Those are separate plans after this RAG foundation is verified.

## File Structure

Create or modify these files after the foundation branch is merged into `main`:

```text
apps/api/
  pyproject.toml
  app/
    api/
      router.py
      routes_ingestion.py
      routes_retrieval.py
    core/
      config.py
    db/
      models.py
    domain/
      rag/
        __init__.py
        chunking.py
        embeddings.py
        ingestion.py
        retrieval.py
        schemas.py
      sources/
        service.py
    infrastructure/
      storage.py
  migrations/
    versions/
      0002_rag_foundation.py
  tests/
    test_rag_chunking.py
    test_rag_embeddings.py
    test_rag_ingestion.py
    test_rag_ingestion_integration.py
    test_rag_retrieval.py
    test_ingestion_routes.py
```

Responsibilities:

- `app/db/models.py`: Add `IngestionJob`, `SourceChunk`, and status enums.
- `app/domain/rag/chunking.py`: Convert normalized extracted text into chunk payloads with stable order and citation metadata.
- `app/domain/rag/embeddings.py`: Define provider interface and deterministic provider for local/test use.
- `app/domain/rag/ingestion.py`: Orchestrate source status, extraction, chunking, embedding, and persistence.
- `app/domain/rag/retrieval.py`: Query chunks by tenant and study space, returning citation-ready results.
- `app/domain/rag/schemas.py`: API request/response models for ingestion and retrieval.
- `app/infrastructure/storage.py`: Add a read-text function for S3/local-compatible object content.
- `app/api/routes_ingestion.py`: Start ingestion for one uploaded source.
- `app/api/routes_retrieval.py`: Retrieve relevant source chunks for a query.

---

### Task 1: Add RAG Dependencies and Settings

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/app/core/config.py`
- Test: `apps/api/tests/test_rag_embeddings.py`

- [ ] **Step 1: Add dependencies**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv add pgvector
```

Expected: `pyproject.toml` and `uv.lock` include `pgvector`.

- [ ] **Step 2: Add RAG settings**

Modify `apps/api/app/core/config.py` so settings include:

```python
rag_embedding_dimension: int = 16
rag_chunk_max_chars: int = 1200
rag_chunk_overlap_chars: int = 180
```

Use conservative defaults because the first provider is deterministic and local. Production model dimensions will be configured when a real provider is added.

- [ ] **Step 3: Write the embedding shape test**

Create `apps/api/tests/test_rag_embeddings.py`:

```python
from app.domain.rag.embeddings import DeterministicEmbeddingProvider


def test_deterministic_embedding_provider_returns_configured_dimension() -> None:
    provider = DeterministicEmbeddingProvider(dimension=16)

    vector = provider.embed_text("gradient descent optimizes loss")

    assert len(vector) == 16
    assert all(isinstance(value, float) for value in vector)
    assert any(value != 0.0 for value in vector)
```

- [ ] **Step 4: Run the test and verify it fails**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_embeddings.py -q
```

Expected: FAIL because `app.domain.rag.embeddings` does not exist.

- [ ] **Step 5: Commit dependency and settings work**

```powershell
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/app/core/config.py apps/api/tests/test_rag_embeddings.py
git commit -m "test: define rag embedding provider contract"
```

---

### Task 2: Implement Embedding Provider Interface

**Files:**
- Create: `apps/api/app/domain/rag/__init__.py`
- Create: `apps/api/app/domain/rag/embeddings.py`
- Test: `apps/api/tests/test_rag_embeddings.py`

- [ ] **Step 1: Implement deterministic provider**

Create `apps/api/app/domain/rag/embeddings.py`:

```python
import hashlib
import math
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError


class DeterministicEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError("Embedding dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        normalized = " ".join(text.lower().split())
        values: list[float] = []
        for index in range(self._dimension):
            digest = hashlib.sha256(f"{index}:{normalized}".encode("utf-8")).digest()
            integer = int.from_bytes(digest[:8], "big", signed=False)
            values.append((integer / ((1 << 64) - 1)) * 2.0 - 1.0)
        length = math.sqrt(sum(value * value for value in values))
        if length == 0:
            return [0.0 for _ in values]
        return [value / length for value in values]
```

Create `apps/api/app/domain/rag/__init__.py`:

```python
"""RAG domain services."""
```

- [ ] **Step 2: Run embedding tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_embeddings.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit provider implementation**

```powershell
git add apps/api/app/domain/rag/__init__.py apps/api/app/domain/rag/embeddings.py apps/api/tests/test_rag_embeddings.py
git commit -m "feat: add deterministic embedding provider"
```

---

### Task 3: Add RAG Database Models and Migration

**Files:**
- Modify: `apps/api/app/db/models.py`
- Create: `apps/api/migrations/versions/0002_rag_foundation.py`
- Test: `apps/api/tests/test_rag_ingestion.py`

- [ ] **Step 1: Write model import test**

Create `apps/api/tests/test_rag_ingestion.py`:

```python
from app.db.models import IngestionJob, IngestionJobStatus, SourceChunk


def test_rag_models_are_importable() -> None:
    assert IngestionJob.__tablename__ == "ingestion_jobs"
    assert SourceChunk.__tablename__ == "source_chunks"
    assert IngestionJobStatus.pending.value == "pending"
```

- [ ] **Step 2: Run model test and verify it fails**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_ingestion.py -q
```

Expected: FAIL because the models do not exist.

- [ ] **Step 3: Add models**

Modify `apps/api/app/db/models.py`:

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
```

Add enums:

```python
class IngestionJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
```

Add relationships to `Source`:

```python
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="source")
    chunks: Mapped[list["SourceChunk"]] = relationship(back_populates="source")
```

Add models:

```python
class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_spaces.id"), nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    status: Mapped[IngestionJobStatus] = mapped_column(
        Enum(IngestionJobStatus, name="ingestion_job_status"),
        nullable=False,
        default=IngestionJobStatus.pending,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped["Source"] = relationship(back_populates="ingestion_jobs")


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index", name="uq_source_chunks_source_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_spaces.id"), nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    citation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped["Source"] = relationship(back_populates="chunks")
```

- [ ] **Step 4: Add Alembic migration**

Create `apps/api/migrations/versions/0002_rag_foundation.py`:

```python
"""rag foundation

Revision ID: 0002_rag_foundation
Revises: 0001_foundation
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_rag_foundation"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    ingestion_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        name="ingestion_job_status",
    )
    ingestion_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_spaces.id"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("status", ingestion_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ingestion_jobs_tenant_id", "ingestion_jobs", ["tenant_id"])
    op.create_index("ix_ingestion_jobs_study_space_id", "ingestion_jobs", ["study_space_id"])
    op.create_index("ix_ingestion_jobs_source_id", "ingestion_jobs", ["source_id"])

    op.create_table(
        "source_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_spaces.id"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("citation", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_id", "chunk_index", name="uq_source_chunks_source_index"),
    )
    op.create_index("ix_source_chunks_tenant_id", "source_chunks", ["tenant_id"])
    op.create_index("ix_source_chunks_study_space_id", "source_chunks", ["study_space_id"])
    op.create_index("ix_source_chunks_source_id", "source_chunks", ["source_id"])
    op.create_index(
        "ix_source_chunks_embedding_hnsw",
        "source_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_source_chunks_embedding_hnsw", table_name="source_chunks")
    op.drop_index("ix_source_chunks_source_id", table_name="source_chunks")
    op.drop_index("ix_source_chunks_study_space_id", table_name="source_chunks")
    op.drop_index("ix_source_chunks_tenant_id", table_name="source_chunks")
    op.drop_table("source_chunks")
    op.drop_index("ix_ingestion_jobs_source_id", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_study_space_id", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_tenant_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    postgresql.ENUM(name="ingestion_job_status").drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 5: Run model test**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_ingestion.py -q
```

Expected: PASS.

- [ ] **Step 6: Validate migration syntax**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run alembic history
```

Expected: Alembic lists `0002_rag_foundation`.

- [ ] **Step 7: Commit models and migration**

```powershell
git add apps/api/app/db/models.py apps/api/migrations/versions/0002_rag_foundation.py apps/api/tests/test_rag_ingestion.py
git commit -m "feat: add rag persistence models"
```

---

### Task 4: Implement Chunking

**Files:**
- Create: `apps/api/app/domain/rag/chunking.py`
- Test: `apps/api/tests/test_rag_chunking.py`

- [ ] **Step 1: Write chunking tests**

Create `apps/api/tests/test_rag_chunking.py`:

```python
from app.domain.rag.chunking import ExtractedDocument, ExtractedPage, chunk_document


def test_chunk_document_keeps_citation_metadata() -> None:
    document = ExtractedDocument(
        source_id="source-1",
        filename="lesson.md",
        pages=[
            ExtractedPage(page_number=1, text="alpha beta gamma " * 120),
            ExtractedPage(page_number=2, text="delta epsilon zeta " * 120),
        ],
    )

    chunks = chunk_document(document, max_chars=300, overlap_chars=40)

    assert len(chunks) > 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].citation["filename"] == "lesson.md"
    assert chunks[0].citation["page_start"] == 1
    assert chunks[-1].citation["page_end"] == 2
    assert chunks[0].token_count > 0


def test_chunk_document_rejects_invalid_overlap() -> None:
    document = ExtractedDocument(
        source_id="source-1",
        filename="lesson.md",
        pages=[ExtractedPage(page_number=1, text="short text")],
    )

    try:
        chunk_document(document, max_chars=100, overlap_chars=100)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
```

- [ ] **Step 2: Run chunking tests and verify they fail**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_chunking.py -q
```

Expected: FAIL because `chunking.py` does not exist.

- [ ] **Step 3: Implement chunking**

Create `apps/api/app/domain/rag/chunking.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    source_id: str
    filename: str
    pages: list[ExtractedPage]


@dataclass(frozen=True)
class ChunkPayload:
    chunk_index: int
    text: str
    token_count: int
    citation: dict


def estimate_token_count(text: str) -> int:
    words = text.split()
    return max(1, int(len(words) * 1.3)) if text.strip() else 0


def normalize_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def chunk_document(
    document: ExtractedDocument,
    max_chars: int,
    overlap_chars: int,
) -> list[ChunkPayload]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars")

    flattened: list[tuple[int, str]] = []
    for page in document.pages:
        text = normalize_text(page.text)
        if text:
            flattened.append((page.page_number, text))

    full_text = "\n\n".join(text for _, text in flattened)
    if not full_text:
        return []

    chunks: list[ChunkPayload] = []
    start = 0
    chunk_index = 0
    while start < len(full_text):
        end = min(start + max_chars, len(full_text))
        if end < len(full_text):
            boundary = full_text.rfind(" ", start, end)
            if boundary > start + int(max_chars * 0.6):
                end = boundary
        text = full_text[start:end].strip()
        page_start, page_end = _page_span(flattened, full_text, start, end)
        if text:
            chunks.append(
                ChunkPayload(
                    chunk_index=chunk_index,
                    text=text,
                    token_count=estimate_token_count(text),
                    citation={
                        "source_id": document.source_id,
                        "filename": document.filename,
                        "page_start": page_start,
                        "page_end": page_end,
                    },
                )
            )
            chunk_index += 1
        if end == len(full_text):
            break
        start = max(0, end - overlap_chars)
    return chunks


def _page_span(
    flattened: list[tuple[int, str]],
    full_text: str,
    start: int,
    end: int,
) -> tuple[int, int]:
    cursor = 0
    touched: list[int] = []
    for page_number, text in flattened:
        page_start = full_text.find(text, cursor)
        page_end = page_start + len(text)
        cursor = page_end
        if page_start <= end and page_end >= start:
            touched.append(page_number)
    if not touched:
        first_page = flattened[0][0]
        return first_page, first_page
    return min(touched), max(touched)
```

- [ ] **Step 4: Run chunking tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_chunking.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit chunking**

```powershell
git add apps/api/app/domain/rag/chunking.py apps/api/tests/test_rag_chunking.py
git commit -m "feat: add citation-aware chunking"
```

---

### Task 5: Add Storage Text Read and Ingestion Service

**Files:**
- Modify: `apps/api/app/infrastructure/storage.py`
- Create: `apps/api/app/domain/rag/ingestion.py`
- Test: `apps/api/tests/test_rag_ingestion.py`
- Test: `apps/api/tests/test_rag_ingestion_integration.py`

- [ ] **Step 1: Extend ingestion tests**

Append to `apps/api/tests/test_rag_ingestion.py`:

```python
import pytest

from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.ingestion import InMemoryTextSourceReader


@pytest.mark.anyio
async def test_in_memory_text_source_reader_reads_known_object() -> None:
    reader = InMemoryTextSourceReader({"objects/intro.md": "hello"})

    assert await reader.read_text("objects/intro.md") == "hello"


def test_deterministic_embedding_provider_is_usable_by_ingestion() -> None:
    provider = DeterministicEmbeddingProvider(dimension=16)

    assert len(provider.embed_text("chapter content")) == 16
```

- [ ] **Step 2: Run ingestion test and verify it fails**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_ingestion.py -q
```

Expected: FAIL because `ingestion.py` does not exist.

- [ ] **Step 3: Add storage reader interface**

Modify `apps/api/app/infrastructure/storage.py` to expose:

```python
from abc import ABC, abstractmethod


class TextSourceReader(ABC):
    @abstractmethod
    async def read_text(self, object_key: str) -> str:
        raise NotImplementedError
```

Keep existing presigned upload behavior unchanged.

- [ ] **Step 4: Implement ingestion service**

Create `apps/api/app/domain/rag/ingestion.py`:

```python
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IngestionJob, IngestionJobStatus, Source, SourceChunk, SourceStatus
from app.domain.rag.chunking import ExtractedDocument, ExtractedPage, chunk_document
from app.domain.rag.embeddings import EmbeddingProvider
from app.infrastructure.storage import TextSourceReader


class InMemoryTextSourceReader(TextSourceReader):
    def __init__(self, objects: dict[str, str]) -> None:
        self._objects = objects

    async def read_text(self, object_key: str) -> str:
        try:
            return self._objects[object_key]
        except KeyError as exc:
            raise FileNotFoundError(object_key) from exc


@dataclass(frozen=True)
class IngestionResult:
    job_id: uuid.UUID
    source_id: uuid.UUID
    status: str
    chunk_count: int


async def ingest_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    reader: TextSourceReader,
    embedding_provider: EmbeddingProvider,
    max_chars: int,
    overlap_chars: int,
) -> IngestionResult:
    source = await session.scalar(select(Source).where(Source.id == source_id))
    if source is None:
        raise ValueError("Source not found")
    if source.status not in {SourceStatus.uploaded, SourceStatus.processing, SourceStatus.failed, SourceStatus.ready}:
        raise ValueError(f"Source must be uploaded before ingestion, got {source.status.value}")

    job = IngestionJob(
        tenant_id=source.tenant_id,
        study_space_id=source.study_space_id,
        source_id=source.id,
        status=IngestionJobStatus.running,
    )
    source.status = SourceStatus.processing
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        text = await reader.read_text(source.object_key)
        document = ExtractedDocument(
            source_id=str(source.id),
            filename=source.filename,
            pages=[ExtractedPage(page_number=1, text=text)],
        )
        chunks = chunk_document(document, max_chars=max_chars, overlap_chars=overlap_chars)
        await session.execute(delete(SourceChunk).where(SourceChunk.source_id == source.id))
        for chunk in chunks:
            session.add(
                SourceChunk(
                    tenant_id=source.tenant_id,
                    study_space_id=source.study_space_id,
                    source_id=source.id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    citation=chunk.citation,
                    embedding=embedding_provider.embed_text(chunk.text),
                    is_active=True,
                )
            )
        job.status = IngestionJobStatus.completed
        job.chunk_count = len(chunks)
        source.status = SourceStatus.ready
        source.error_message = None
        await session.commit()
        return IngestionResult(
            job_id=job.id,
            source_id=source.id,
            status=job.status.value,
            chunk_count=job.chunk_count,
        )
    except Exception as exc:
        job.status = IngestionJobStatus.failed
        job.error_message = str(exc)
        source.status = SourceStatus.failed
        source.error_message = str(exc)
        await session.commit()
        raise
```

- [ ] **Step 5: Add Postgres integration test for persistence**

Create `apps/api/tests/test_rag_ingestion_integration.py`:

```python
import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Source, SourceStatus, StudySpace, Tenant, User
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.ingestion import InMemoryTextSourceReader, ingest_source


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Postgres integration tests require RUN_POSTGRES_TESTS=1 and DATABASE_URL",
)


@pytest.mark.anyio
async def test_ingest_source_creates_chunks_and_marks_source_ready() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        tenant_id = uuid.uuid4()
        owner_user_id = uuid.uuid4()
        study_space_id = uuid.uuid4()
        session.add(Tenant(id=tenant_id, name="Test Tenant"))
        session.add(User(id=owner_user_id, email=f"{owner_user_id}@example.com", display_name="Test User"))
        session.add(
            StudySpace(
                id=study_space_id,
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                name="Linear Algebra",
                goal="Learn gradients",
                level="beginner",
                intensity="normal",
                target_days=14,
                route_outline=[],
            )
        )
        source = Source(
            tenant_id=tenant_id,
            study_space_id=study_space_id,
            filename="intro.md",
            content_type="text/markdown",
            object_key="tenants/t/spaces/s/sources/source/intro.md",
            status=SourceStatus.uploaded,
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)

        result = await ingest_source(
            session=session,
            source_id=source.id,
            reader=InMemoryTextSourceReader(
                {
                    source.object_key: "# Intro\n\nGradient descent updates model parameters. " * 40,
                }
            ),
            embedding_provider=DeterministicEmbeddingProvider(dimension=16),
            max_chars=300,
            overlap_chars=40,
        )

        await session.refresh(source)
        assert result.status == "completed"
        assert result.chunk_count > 0
        assert source.status == SourceStatus.ready
    await engine.dispose()
```

- [ ] **Step 6: Run unit ingestion tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_ingestion.py -q
```

Expected: PASS.

- [ ] **Step 7: Run optional Postgres integration test**

Start local infra from repo root:

```powershell
docker compose -f infra/docker-compose.yml up -d postgres
```

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:RUN_POSTGRES_TESTS = "1"
$env:DATABASE_URL = "postgresql+asyncpg://study_agent:study_agent@localhost:5432/study_agent"
uv run pytest tests/test_rag_ingestion_integration.py -q
```

Expected: PASS when local Postgres is running with the `vector` extension.

- [ ] **Step 8: Commit ingestion service**

```powershell
git add apps/api/app/infrastructure/storage.py apps/api/app/domain/rag/ingestion.py apps/api/tests/test_rag_ingestion.py apps/api/tests/test_rag_ingestion_integration.py
git commit -m "feat: ingest uploaded text sources"
```

---

### Task 6: Implement Scoped Retrieval

**Files:**
- Create: `apps/api/app/domain/rag/retrieval.py`
- Create: `apps/api/app/domain/rag/schemas.py`
- Test: `apps/api/tests/test_rag_retrieval.py`

- [ ] **Step 1: Write retrieval unit test**

Create `apps/api/tests/test_rag_retrieval.py`:

```python
import uuid

from app.domain.rag.retrieval import RetrievedChunk, rank_chunks_by_dot_product


def test_rank_chunks_by_dot_product_orders_relevant_chunks() -> None:
    tenant_id = uuid.uuid4()
    space_id = uuid.uuid4()
    chunks = [
        RetrievedChunk(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            study_space_id=space_id,
            source_id=uuid.uuid4(),
            chunk_index=0,
            text="unrelated cooking note",
            citation={"filename": "a.md"},
            embedding=[1.0, 0.0],
            score=0.0,
        ),
        RetrievedChunk(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            study_space_id=space_id,
            source_id=uuid.uuid4(),
            chunk_index=1,
            text="gradient descent learning rate",
            citation={"filename": "b.md"},
            embedding=[0.0, 1.0],
            score=0.0,
        ),
    ]

    ranked = rank_chunks_by_dot_product(query_embedding=[0.0, 1.0], chunks=chunks, limit=1)

    assert ranked[0].text == "gradient descent learning rate"
    assert ranked[0].score == 1.0
```

- [ ] **Step 2: Run retrieval test and verify it fails**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_retrieval.py -q
```

Expected: FAIL because retrieval module does not exist.

- [ ] **Step 3: Add schemas**

Create `apps/api/app/domain/rag/schemas.py`:

```python
import uuid

from pydantic import BaseModel, Field


class IngestSourceRequest(BaseModel):
    source_id: uuid.UUID


class IngestSourceResponse(BaseModel):
    job_id: uuid.UUID
    source_id: uuid.UUID
    status: str
    chunk_count: int


class RetrieveRequest(BaseModel):
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class RetrievedChunkResponse(BaseModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    chunk_index: int
    text: str
    citation: dict
    score: float


class RetrieveResponse(BaseModel):
    query: str
    chunks: list[RetrievedChunkResponse]
```

- [ ] **Step 4: Implement retrieval ranking and database query**

Create `apps/api/app/domain/rag/retrieval.py`:

```python
import uuid
from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SourceChunk
from app.domain.rag.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class RetrievedChunk:
    id: uuid.UUID
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    source_id: uuid.UUID
    chunk_index: int
    text: str
    citation: dict
    embedding: list[float]
    score: float


def dot_product(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def rank_chunks_by_dot_product(
    query_embedding: list[float],
    chunks: list[RetrievedChunk],
    limit: int,
) -> list[RetrievedChunk]:
    scored = [replace(chunk, score=dot_product(query_embedding, chunk.embedding)) for chunk in chunks]
    return sorted(scored, key=lambda chunk: chunk.score, reverse=True)[:limit]


async def retrieve_chunks(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    query: str,
    limit: int,
    embedding_provider: EmbeddingProvider,
) -> list[RetrievedChunk]:
    query_embedding = embedding_provider.embed_text(query)
    rows = await session.scalars(
        select(SourceChunk).where(
            SourceChunk.tenant_id == tenant_id,
            SourceChunk.study_space_id == study_space_id,
            SourceChunk.is_active.is_(True),
        )
    )
    chunks = [
        RetrievedChunk(
            id=row.id,
            tenant_id=row.tenant_id,
            study_space_id=row.study_space_id,
            source_id=row.source_id,
            chunk_index=row.chunk_index,
            text=row.text,
            citation=row.citation,
            embedding=list(row.embedding),
            score=0.0,
        )
        for row in rows
    ]
    return rank_chunks_by_dot_product(query_embedding=query_embedding, chunks=chunks, limit=limit)
```

This keeps tests database-portable. A follow-up optimization can replace in-Python ranking with pgvector SQL ordering once integration tests run against Postgres in CI.

- [ ] **Step 5: Run retrieval tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_retrieval.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit retrieval domain**

```powershell
git add apps/api/app/domain/rag/retrieval.py apps/api/app/domain/rag/schemas.py apps/api/tests/test_rag_retrieval.py
git commit -m "feat: add scoped rag retrieval"
```

---

### Task 7: Add Ingestion and Retrieval API Routes

**Files:**
- Create: `apps/api/app/api/routes_ingestion.py`
- Create: `apps/api/app/api/routes_retrieval.py`
- Modify: `apps/api/app/api/router.py`
- Test: `apps/api/tests/test_ingestion_routes.py`

- [ ] **Step 1: Write route registration test**

Create `apps/api/tests/test_ingestion_routes.py`:

```python
from app.main import app


def test_rag_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/api/v1/ingestion/sources/{source_id}/run" in paths
    assert "/api/v1/rag/retrieve" in paths
```

- [ ] **Step 2: Run route test and verify it fails**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_ingestion_routes.py -q
```

Expected: FAIL because routes are not registered.

- [ ] **Step 3: Create ingestion route**

Create `apps/api/app/api/routes_ingestion.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.ingestion import IngestionResult, ingest_source
from app.domain.rag.schemas import IngestSourceResponse
from app.infrastructure.storage import TextSourceReader

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class UnsupportedRuntimeTextReader(TextSourceReader):
    async def read_text(self, object_key: str) -> str:
        raise RuntimeError(f"Runtime text reader is not configured for {object_key}")


@router.post("/sources/{source_id}/run", response_model=IngestSourceResponse)
async def run_source_ingestion(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> IngestSourceResponse:
    settings = get_settings()
    try:
        result: IngestionResult = await ingest_source(
            session=session,
            source_id=source_id,
            reader=UnsupportedRuntimeTextReader(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=settings.rag_embedding_dimension),
            max_chars=settings.rag_chunk_max_chars,
            overlap_chars=settings.rag_chunk_overlap_chars,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return IngestSourceResponse(
        job_id=result.job_id,
        source_id=result.source_id,
        status=result.status,
        chunk_count=result.chunk_count,
    )
```

The `501` response makes the interface visible while preventing false success until object-storage text reading is configured. Unit tests for ingestion use `InMemoryTextSourceReader`.

- [ ] **Step 4: Create retrieval route**

Create `apps/api/app/api/routes_retrieval.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.domain.rag.embeddings import DeterministicEmbeddingProvider
from app.domain.rag.retrieval import retrieve_chunks
from app.domain.rag.schemas import RetrieveRequest, RetrievedChunkResponse, RetrieveResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(
    payload: RetrieveRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RetrieveResponse:
    settings = get_settings()
    chunks = await retrieve_chunks(
        session=session,
        tenant_id=payload.tenant_id,
        study_space_id=payload.study_space_id,
        query=payload.query,
        limit=payload.limit,
        embedding_provider=DeterministicEmbeddingProvider(dimension=settings.rag_embedding_dimension),
    )
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

- [ ] **Step 5: Register routes**

Modify `apps/api/app/api/router.py`:

```python
from app.api import routes_health, routes_ingestion, routes_retrieval, routes_study_spaces, routes_uploads

api_router.include_router(routes_ingestion.router)
api_router.include_router(routes_retrieval.router)
```

Keep existing route registrations unchanged.

- [ ] **Step 6: Run route tests**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_ingestion_routes.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit API routes**

```powershell
git add apps/api/app/api/routes_ingestion.py apps/api/app/api/routes_retrieval.py apps/api/app/api/router.py apps/api/tests/test_ingestion_routes.py
git commit -m "feat: expose rag ingestion and retrieval routes"
```

---

### Task 8: Full Verification and Documentation

**Files:**
- Modify: `README.md`
- Modify: `apps/api/README.md`

- [ ] **Step 1: Document RAG foundation behavior**

Add to `README.md`:

```markdown
### RAG foundation

The API includes the first RAG foundation:

- uploaded source metadata can be ingested into chunks;
- chunks store citation metadata and embeddings;
- retrieval is scoped by tenant and study space;
- deterministic embeddings are used for local development and tests.

The first runtime ingestion endpoint exposes the API shape but returns `501` until object-storage text reading is configured. Domain tests cover the ingestion path with an in-memory text reader.
```

Add to `apps/api/README.md`:

```markdown
## RAG domain

Core files:

- `app/domain/rag/chunking.py`: normalized text to citation-ready chunks.
- `app/domain/rag/embeddings.py`: embedding provider contract and deterministic local provider.
- `app/domain/rag/ingestion.py`: source-to-chunks orchestration.
- `app/domain/rag/retrieval.py`: tenant- and space-scoped retrieval.

Run RAG tests:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest tests/test_rag_chunking.py tests/test_rag_embeddings.py tests/test_rag_ingestion.py tests/test_rag_retrieval.py tests/test_ingestion_routes.py -q
```
```

- [ ] **Step 2: Run API verification**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest -q
```

Expected: all API tests PASS.

- [ ] **Step 3: Run lint**

Run from `apps/api`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run ruff check .
```

Expected: PASS.

- [ ] **Step 4: Validate Docker Compose still parses**

Run from repo root:

```powershell
docker compose -f infra/docker-compose.yml config
```

Expected: exit code 0. A Docker credential warning can be recorded as environment-related if the compose config is printed successfully.

- [ ] **Step 5: Commit docs**

```powershell
git add README.md apps/api/README.md
git commit -m "docs: describe rag foundation"
```

---

## Final Verification

Run from repo root and record the results in the PR description:

```powershell
cd apps/api
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run pytest -q
uv run ruff check .
cd ..\..
docker compose -f infra/docker-compose.yml config
```

Expected:

- API tests pass.
- Ruff passes.
- Docker Compose config exits 0.

Postgres vector storage is verified only after the optional integration command in Task 5 passes with `RUN_POSTGRES_TESTS=1`.

## Execution Order

1. Merge PR #1 into `main`.
2. Create a new branch: `codex/rag-foundation`.
3. Execute Tasks 1-8 in order.
4. Push branch and open PR.
5. In the PR, explicitly call out that PDF/OCR, real embedding providers, background workers, and LangGraph are planned follow-ups.

## Self-Review

- Spec coverage: This plan implements the approved RAG foundation layer: source chunk index, scoped retrieval, citation construction, and provider abstraction. It does not implement agents or chat because those are later milestones in the approved product flow.
- Placeholder scan: No task relies on undefined behavior. Runtime object storage text reading is intentionally represented by a `501` route guard while domain ingestion is testable through an in-memory reader.
- Type consistency: `IngestionJob`, `SourceChunk`, `IngestionResult`, `RetrieveRequest`, and `RetrievedChunk` names are consistent across tasks.
- Scope control: The plan is one independently testable subsystem and should not be expanded with frontend or LangGraph work.
