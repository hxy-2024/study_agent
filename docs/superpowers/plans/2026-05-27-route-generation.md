# Route Generation Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist learning routes and chapters, generate deterministic route drafts from study spaces and source chunks, expose tenant-safe route APIs, and lightly connect the study-space frontend.

**Architecture:** Add a focused `routes` backend domain with generator, schemas, service, and API modules. Keep deterministic generation behind a `RouteGenerator` protocol so a future LangGraph/LLM generator can replace it. Frontend changes stay local to `apps/web/pages/spaces/[id]/index.vue` and must preserve existing source-library behavior.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.x async, Alembic, Postgres JSONB, pytest, httpx ASGI tests, Nuxt 4, Vue 3, TypeScript, Vitest, Vue Test Utils.

---

## Scope Check

This plan implements:

`docs/superpowers/specs/2026-05-27-route-generation-design.md`

Execution base:

- `main` after `merge: frontend app shell`.
- Existing frontend source-library tests should exist in `apps/web/tests/source-library.spec.ts`.

In scope:

- `learning_routes` and `chapters` persistence.
- Deterministic route generator.
- Tenant-safe draft/list/active-chapters/activate APIs.
- Compatibility update of `StudySpace.route_outline` on activation.
- Study-space detail frontend route panel with generate and activate actions.
- Backend and frontend tests.

Out of scope:

- Real LLM calls.
- LangGraph workflow.
- Streaming generation.
- Route editing/diff UI.
- Chapter study page.
- Chat, quiz, mastery, review cards.
- Background workers.

## File Structure

```text
apps/api/
  app/
    api/
      router.py
      routes_learning_routes.py
    db/
      models.py
    domain/
      learning_routes/
        __init__.py
        generator.py
        schemas.py
        service.py
      study_spaces/
        service.py
  migrations/
    versions/
      0003_learning_routes.py
  tests/
    test_learning_route_generator.py
    test_learning_route_service.py
    test_learning_route_routes.py
    test_models.py

apps/web/
  pages/
    spaces/
      [id]/
        index.vue
  tests/
    source-library.spec.ts
```

Responsibilities:

- `app/db/models.py`: SQLAlchemy enums and models for learning routes and chapters.
- `migrations/versions/0003_learning_routes.py`: database schema migration and enum lifecycle.
- `app/domain/learning_routes/generator.py`: generator protocol, request/result dataclasses, deterministic generator.
- `app/domain/learning_routes/schemas.py`: Pydantic API schemas.
- `app/domain/learning_routes/service.py`: tenant-safe persistence, chunk loading, draft generation, list routes, active chapters, activation.
- `app/api/routes_learning_routes.py`: FastAPI endpoints and HTTP error mapping.
- `apps/web/pages/spaces/[id]/index.vue`: route panel state and API calls, preserving source-library code.
- `apps/web/tests/source-library.spec.ts`: existing tests plus route panel behavior tests.

---

### Task 1: Add Learning Route Models and Migration

**Files:**
- Modify: `apps/api/app/db/models.py`
- Create: `apps/api/migrations/versions/0003_learning_routes.py`
- Modify: `apps/api/tests/test_models.py`

- [ ] **Step 1: Add failing model tests**

Append to `apps/api/tests/test_models.py`:

```python
from app.db.models import Chapter, ChapterStatus, LearningRoute, LearningRouteStatus


def test_learning_route_models_have_expected_tables() -> None:
    assert LearningRoute.__tablename__ == "learning_routes"
    assert Chapter.__tablename__ == "chapters"
    assert LearningRouteStatus.draft.value == "draft"
    assert LearningRouteStatus.active.value == "active"
    assert LearningRouteStatus.archived.value == "archived"
    assert ChapterStatus.not_started.value == "not_started"
```

- [ ] **Step 2: Run model test to verify failure**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
python -m pytest tests/test_models.py -q
```

Expected: FAIL because `LearningRoute`, `Chapter`, and enums do not exist.

- [ ] **Step 3: Add enums and relationships to models**

Modify `apps/api/app/db/models.py`.

Add after `IngestionJobStatus`:

```python
class LearningRouteStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ChapterStatus(str, enum.Enum):
    not_started = "not_started"
    active = "active"
    completed = "completed"
```

Inside `StudySpace`, add:

```python
    learning_routes: Mapped[list["LearningRoute"]] = relationship(back_populates="study_space")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="study_space")
```

After `SourceChunk`, add:

```python
class LearningRoute(Base):
    __tablename__ = "learning_routes"
    __table_args__ = (
        UniqueConstraint("study_space_id", "version", name="uq_learning_routes_space_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_spaces.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[LearningRouteStatus] = mapped_column(
        Enum(LearningRouteStatus, name="learning_route_status"),
        nullable=False,
        default=LearningRouteStatus.draft,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    generation_strategy: Mapped[str] = mapped_column(String(80), nullable=False, default="deterministic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    study_space: Mapped["StudySpace"] = relationship(back_populates="learning_routes")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="learning_route")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("learning_route_id", "order_index", name="uq_chapters_route_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_spaces.id"), nullable=False, index=True)
    learning_route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_routes.id"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ChapterStatus] = mapped_column(
        Enum(ChapterStatus, name="chapter_status"),
        nullable=False,
        default=ChapterStatus.not_started,
    )
    source_chunk_refs: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study_space: Mapped["StudySpace"] = relationship(back_populates="chapters")
    learning_route: Mapped["LearningRoute"] = relationship(back_populates="chapters")
```

- [ ] **Step 4: Create Alembic migration**

Create `apps/api/migrations/versions/0003_learning_routes.py`:

```python
"""learning routes

Revision ID: 0003_learning_routes
Revises: 0002_rag_foundation
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_learning_routes"
down_revision: str | None = "0002_rag_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    route_status = postgresql.ENUM("draft", "active", "archived", name="learning_route_status")
    chapter_status = postgresql.ENUM("not_started", "active", "completed", name="chapter_status")
    route_status.create(op.get_bind(), checkfirst=True)
    chapter_status.create(op.get_bind(), checkfirst=True)

    route_status_column = postgresql.ENUM(
        "draft",
        "active",
        "archived",
        name="learning_route_status",
        create_type=False,
    )
    chapter_status_column = postgresql.ENUM(
        "not_started",
        "active",
        "completed",
        name="chapter_status",
        create_type=False,
    )

    op.create_table(
        "learning_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_spaces.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", route_status_column, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("generation_strategy", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("study_space_id", "version", name="uq_learning_routes_space_version"),
    )
    op.create_index("ix_learning_routes_tenant_id", "learning_routes", ["tenant_id"])
    op.create_index("ix_learning_routes_study_space_id", "learning_routes", ["study_space_id"])

    op.create_table(
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_spaces.id"), nullable=False),
        sa.Column("learning_route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_routes.id"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("estimated_days", sa.Integer(), nullable=False),
        sa.Column("status", chapter_status_column, nullable=False),
        sa.Column("source_chunk_refs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("learning_route_id", "order_index", name="uq_chapters_route_order"),
    )
    op.create_index("ix_chapters_tenant_id", "chapters", ["tenant_id"])
    op.create_index("ix_chapters_study_space_id", "chapters", ["study_space_id"])
    op.create_index("ix_chapters_learning_route_id", "chapters", ["learning_route_id"])


def downgrade() -> None:
    op.drop_index("ix_chapters_learning_route_id", table_name="chapters")
    op.drop_index("ix_chapters_study_space_id", table_name="chapters")
    op.drop_index("ix_chapters_tenant_id", table_name="chapters")
    op.drop_table("chapters")
    op.drop_index("ix_learning_routes_study_space_id", table_name="learning_routes")
    op.drop_index("ix_learning_routes_tenant_id", table_name="learning_routes")
    op.drop_table("learning_routes")
    postgresql.ENUM(name="chapter_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="learning_route_status").drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 5: Run model and migration checks**

Run:

```powershell
python -m pytest tests/test_models.py -q
python -m alembic history
```

Expected: PASS and Alembic history includes `0003_learning_routes`.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/db/models.py apps/api/migrations/versions/0003_learning_routes.py apps/api/tests/test_models.py
git commit -m "feat: add learning route models"
```

---

### Task 2: Add Deterministic Route Generator

**Files:**
- Create: `apps/api/app/domain/learning_routes/__init__.py`
- Create: `apps/api/app/domain/learning_routes/generator.py`
- Create: `apps/api/tests/test_learning_route_generator.py`
- Modify: `apps/api/app/domain/study_spaces/service.py`
- Modify: `apps/api/tests/test_study_spaces.py`

- [ ] **Step 1: Write generator tests**

Create `apps/api/tests/test_learning_route_generator.py`:

```python
import uuid

import pytest

from app.domain.learning_routes.generator import (
    DeterministicRouteGenerator,
    RouteGenerationRequest,
    SourceChunkExcerpt,
)


@pytest.mark.anyio
async def test_deterministic_generator_uses_goal_without_chunks() -> None:
    generator = DeterministicRouteGenerator()

    result = await generator.generate(
        RouteGenerationRequest(
            tenant_id=uuid.uuid4(),
            study_space_id=uuid.uuid4(),
            study_space_name="Linear Algebra",
            goal="Understand matrices",
            level="beginner",
            intensity="normal",
            target_days=14,
            max_chapters=5,
            chunks=[],
        )
    )

    assert result.generation_strategy == "deterministic"
    assert result.title == "Linear Algebra learning route"
    assert len(result.chapters) == 3
    assert result.chapters[0].title == "Clarify the learning goal"
    assert "Understand matrices" in result.chapters[0].goal
    assert sum(chapter.estimated_days for chapter in result.chapters) == 14


@pytest.mark.anyio
async def test_deterministic_generator_uses_chunk_references() -> None:
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    generator = DeterministicRouteGenerator()

    result = await generator.generate(
        RouteGenerationRequest(
            tenant_id=uuid.uuid4(),
            study_space_id=uuid.uuid4(),
            study_space_name="RAG Basics",
            goal="Learn retrieval",
            level="intermediate",
            intensity="normal",
            target_days=10,
            max_chapters=4,
            chunks=[
                SourceChunkExcerpt(
                    source_id=source_id,
                    chunk_id=chunk_id,
                    chunk_index=0,
                    text="Embeddings convert text into vectors for semantic retrieval.",
                )
            ],
        )
    )

    assert len(result.chapters) == 1
    assert result.chapters[0].title == "Embeddings convert text into vectors"
    assert result.chapters[0].source_chunk_refs == [
        {
            "source_id": str(source_id),
            "chunk_id": str(chunk_id),
            "chunk_index": 0,
        }
    ]
```

- [ ] **Step 2: Run generator tests to verify failure**

Run:

```powershell
python -m pytest tests/test_learning_route_generator.py -q
```

Expected: FAIL because `app.domain.learning_routes.generator` does not exist.

- [ ] **Step 3: Create generator module**

Create `apps/api/app/domain/learning_routes/__init__.py`:

```python
"""Learning route domain."""
```

Create `apps/api/app/domain/learning_routes/generator.py`:

```python
import re
import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SourceChunkExcerpt:
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    text: str


@dataclass(frozen=True)
class RouteGenerationRequest:
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    study_space_name: str
    goal: str
    level: str
    intensity: str
    target_days: int
    max_chapters: int
    chunks: list[SourceChunkExcerpt]


@dataclass(frozen=True)
class ChapterDraft:
    title: str
    goal: str
    summary: str
    estimated_days: int
    source_chunk_refs: list[dict]


@dataclass(frozen=True)
class RouteGenerationResult:
    title: str
    summary: str
    generation_strategy: str
    chapters: list[ChapterDraft]


class RouteGenerator(Protocol):
    async def generate(self, request: RouteGenerationRequest) -> RouteGenerationResult:
        ...


class DeterministicRouteGenerator:
    async def generate(self, request: RouteGenerationRequest) -> RouteGenerationResult:
        chunks = request.chunks[: request.max_chapters]
        if chunks:
            chapters = self._chapters_from_chunks(request=request, chunks=chunks)
        else:
            chapters = self._fallback_chapters(request)

        return RouteGenerationResult(
            title=f"{request.study_space_name} learning route",
            summary=f"A {len(chapters)} chapter route for {request.goal}.",
            generation_strategy="deterministic",
            chapters=chapters,
        )

    def _chapters_from_chunks(
        self,
        request: RouteGenerationRequest,
        chunks: list[SourceChunkExcerpt],
    ) -> list[ChapterDraft]:
        days = split_days(request.target_days, len(chunks))
        chapters: list[ChapterDraft] = []
        for index, chunk in enumerate(chunks):
            title = title_from_text(chunk.text)
            chapters.append(
                ChapterDraft(
                    title=title,
                    goal=f"Understand how this source material supports: {request.goal}.",
                    summary=excerpt(chunk.text, 220),
                    estimated_days=days[index],
                    source_chunk_refs=[
                        {
                            "source_id": str(chunk.source_id),
                            "chunk_id": str(chunk.chunk_id),
                            "chunk_index": chunk.chunk_index,
                        }
                    ],
                )
            )
        return chapters

    def _fallback_chapters(self, request: RouteGenerationRequest) -> list[ChapterDraft]:
        days = split_days(request.target_days, 3)
        return [
            ChapterDraft(
                title="Clarify the learning goal",
                goal=f"Define the scope and success criteria for {request.goal}.",
                summary="Map the target outcome, prior knowledge, and constraints before studying details.",
                estimated_days=days[0],
                source_chunk_refs=[],
            ),
            ChapterDraft(
                title="Build the core knowledge map",
                goal=f"Learn the central concepts needed to achieve {request.goal}.",
                summary="Organize the main ideas into a usable structure and connect related concepts.",
                estimated_days=days[1],
                source_chunk_refs=[],
            ),
            ChapterDraft(
                title="Review, test, and reinforce",
                goal=f"Check understanding and reinforce weak areas for {request.goal}.",
                summary="Use review, practice, and self-testing to convert the route into retained knowledge.",
                estimated_days=days[2],
                source_chunk_refs=[],
            ),
        ]


def split_days(total_days: int, chapter_count: int) -> list[int]:
    safe_total = max(1, total_days)
    safe_count = max(1, chapter_count)
    base = max(1, safe_total // safe_count)
    days = [base for _ in range(safe_count)]
    remainder = safe_total - sum(days)
    index = 0
    while remainder > 0:
        days[index % safe_count] += 1
        remainder -= 1
        index += 1
    return days


def title_from_text(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return "Source guided study"
    return " ".join(words[:5])


def excerpt(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}..."
```

- [ ] **Step 4: Replace study-space compatibility helper**

Modify `apps/api/app/domain/study_spaces/service.py`.

Replace `create_route_outline` with:

```python
from app.domain.learning_routes.generator import DeterministicRouteGenerator, RouteGenerationRequest


async def create_route_outline(goal: str, target_days: int) -> list[dict]:
    result = await DeterministicRouteGenerator().generate(
        RouteGenerationRequest(
            tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            study_space_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            study_space_name="Study space",
            goal=goal,
            level="beginner",
            intensity="normal",
            target_days=target_days,
            max_chapters=3,
            chunks=[],
        )
    )
    return [
        {
            "order": index,
            "title": chapter.title,
            "description": chapter.summary,
            "estimated_days": chapter.estimated_days,
        }
        for index, chapter in enumerate(result.chapters, start=1)
    ]
```

Then update `create_study_space` to await it:

```python
        route_outline=await create_route_outline(payload.goal, payload.target_days),
```

Add `import uuid` at the top of `service.py`.

- [ ] **Step 5: Update study-space tests**

Modify `apps/api/tests/test_study_spaces.py`:

```python
import uuid

import pytest

from app.domain.study_spaces.service import create_route_outline


@pytest.mark.anyio
async def test_create_route_outline_uses_goal_when_no_ai_is_available() -> None:
    outline = await create_route_outline(goal="Learn linear algebra", target_days=14)

    assert outline[0]["title"] == "Clarify the learning goal"
    assert "linear algebra" in outline[0]["description"].lower()
    assert outline[-1]["title"] == "Review, test, and reinforce"
    assert sum(chapter["estimated_days"] for chapter in outline) == 14


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

- [ ] **Step 6: Run generator and study-space tests**

Run:

```powershell
python -m pytest tests/test_learning_route_generator.py tests/test_study_spaces.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/app/domain/learning_routes apps/api/app/domain/study_spaces/service.py apps/api/tests/test_learning_route_generator.py apps/api/tests/test_study_spaces.py
git commit -m "feat: add deterministic route generator"
```

---

### Task 3: Add Learning Route Service

**Files:**
- Create: `apps/api/app/domain/learning_routes/schemas.py`
- Create: `apps/api/app/domain/learning_routes/service.py`
- Create: `apps/api/tests/test_learning_route_service.py`

- [ ] **Step 1: Write service tests with fake session objects**

Create `apps/api/tests/test_learning_route_service.py`:

```python
import uuid
from types import SimpleNamespace

import pytest

from app.db.models import ChapterStatus, LearningRouteStatus, SourceChunk, StudySpace
from app.domain.learning_routes.generator import DeterministicRouteGenerator
from app.domain.learning_routes.service import (
    build_route_outline,
    collect_chunk_excerpts,
    persist_generated_route,
)


def make_study_space(tenant_id: uuid.UUID, study_space_id: uuid.UUID) -> StudySpace:
    return StudySpace(
        id=study_space_id,
        tenant_id=tenant_id,
        owner_user_id=uuid.uuid4(),
        name="RAG Basics",
        goal="Learn retrieval",
        level="beginner",
        intensity="normal",
        target_days=9,
    )


@pytest.mark.anyio
async def test_collect_chunk_excerpts_limits_text() -> None:
    source_id = uuid.uuid4()
    chunk = SourceChunk(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        source_id=source_id,
        chunk_index=0,
        text="x" * 600,
        token_count=10,
        citation={},
        embedding=[0.1] * 16,
        is_active=True,
    )

    excerpts = collect_chunk_excerpts([chunk], max_excerpt_chars=500)

    assert len(excerpts) == 1
    assert excerpts[0].source_id == source_id
    assert len(excerpts[0].text) == 500


@pytest.mark.anyio
async def test_persist_generated_route_creates_draft_route_and_chapters() -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    study_space = make_study_space(tenant_id, study_space_id)
    added = []

    class FakeSession:
        def add(self, obj) -> None:
            added.append(obj)

        async def flush(self) -> None:
            for obj in added:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()

    route, chapters = await persist_generated_route(
        session=FakeSession(),
        study_space=study_space,
        version=1,
        chunks=[],
        generator=DeterministicRouteGenerator(),
        max_chapters=5,
    )

    assert route.status == LearningRouteStatus.draft
    assert route.tenant_id == tenant_id
    assert route.study_space_id == study_space_id
    assert len(chapters) == 3
    assert chapters[0].status == ChapterStatus.not_started
    assert chapters[0].learning_route_id == route.id


def test_build_route_outline_maps_chapters() -> None:
    chapters = [
        SimpleNamespace(order_index=1, title="Intro", summary="Start", estimated_days=2),
        SimpleNamespace(order_index=2, title="Practice", summary="Apply", estimated_days=3),
    ]

    assert build_route_outline(chapters) == [
        {"order": 1, "title": "Intro", "description": "Start", "estimated_days": 2},
        {"order": 2, "title": "Practice", "description": "Apply", "estimated_days": 3},
    ]
```

- [ ] **Step 2: Run service tests to verify failure**

Run:

```powershell
python -m pytest tests/test_learning_route_service.py -q
```

Expected: FAIL because `learning_routes.service` does not exist.

- [ ] **Step 3: Add API schemas**

Create `apps/api/app/domain/learning_routes/schemas.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RouteDraftRequest(BaseModel):
    max_chapters: int = Field(default=5, ge=3, le=8)


class LearningRouteResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    version: int
    status: str
    title: str
    summary: str
    generation_strategy: str
    created_at: datetime | None = None
    activated_at: datetime | None = None


class ChapterResponse(BaseModel):
    id: uuid.UUID
    learning_route_id: uuid.UUID
    order_index: int
    title: str
    goal: str
    summary: str
    estimated_days: int
    status: str
    source_chunk_refs: list[dict]


class RouteWithChaptersResponse(BaseModel):
    route: LearningRouteResponse
    chapters: list[ChapterResponse]


class RoutesListResponse(BaseModel):
    routes: list[RouteWithChaptersResponse]


class ChaptersListResponse(BaseModel):
    chapters: list[ChapterResponse]
```

- [ ] **Step 4: Add service module**

Create `apps/api/app/domain/learning_routes/service.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Chapter,
    ChapterStatus,
    LearningRoute,
    LearningRouteStatus,
    SourceChunk,
    StudySpace,
)
from app.domain.learning_routes.generator import (
    RouteGenerator,
    RouteGenerationRequest,
    SourceChunkExcerpt,
)
from app.domain.sources.service import ensure_study_space_in_tenant


def collect_chunk_excerpts(
    chunks: list[SourceChunk],
    max_excerpt_chars: int,
) -> list[SourceChunkExcerpt]:
    return [
        SourceChunkExcerpt(
            source_id=chunk.source_id,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            text=chunk.text[:max_excerpt_chars],
        )
        for chunk in chunks
    ]


async def load_route_source_chunks(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    max_chunks: int = 24,
) -> list[SourceChunk]:
    rows = await session.scalars(
        select(SourceChunk)
        .where(
            SourceChunk.tenant_id == tenant_id,
            SourceChunk.study_space_id == study_space_id,
            SourceChunk.is_active.is_(True),
        )
        .order_by(SourceChunk.source_id, SourceChunk.chunk_index)
        .limit(max_chunks)
    )
    return list(rows)


async def next_route_version(
    session: AsyncSession,
    study_space_id: uuid.UUID,
) -> int:
    current = await session.scalar(
        select(func.max(LearningRoute.version)).where(LearningRoute.study_space_id == study_space_id)
    )
    return int(current or 0) + 1


async def persist_generated_route(
    session,
    study_space: StudySpace,
    version: int,
    chunks: list[SourceChunk],
    generator: RouteGenerator,
    max_chapters: int,
) -> tuple[LearningRoute, list[Chapter]]:
    excerpts = collect_chunk_excerpts(chunks, max_excerpt_chars=500)
    result = await generator.generate(
        RouteGenerationRequest(
            tenant_id=study_space.tenant_id,
            study_space_id=study_space.id,
            study_space_name=study_space.name,
            goal=study_space.goal,
            level=study_space.level,
            intensity=study_space.intensity,
            target_days=study_space.target_days,
            max_chapters=max_chapters,
            chunks=excerpts,
        )
    )
    if not result.chapters:
        raise ValueError("Route generation produced no chapters")

    route = LearningRoute(
        tenant_id=study_space.tenant_id,
        study_space_id=study_space.id,
        version=version,
        status=LearningRouteStatus.draft,
        title=result.title,
        summary=result.summary,
        generation_strategy=result.generation_strategy,
    )
    session.add(route)
    await session.flush()

    chapters = [
        Chapter(
            tenant_id=study_space.tenant_id,
            study_space_id=study_space.id,
            learning_route_id=route.id,
            order_index=index,
            title=chapter.title,
            goal=chapter.goal,
            summary=chapter.summary,
            estimated_days=chapter.estimated_days,
            status=ChapterStatus.not_started,
            source_chunk_refs=chapter.source_chunk_refs,
        )
        for index, chapter in enumerate(result.chapters, start=1)
    ]
    for chapter in chapters:
        session.add(chapter)
    await session.flush()
    return route, chapters


async def create_route_draft(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
    generator: RouteGenerator,
    max_chapters: int,
) -> tuple[LearningRoute, list[Chapter]]:
    study_space = await ensure_study_space_in_tenant(
        session=session,
        study_space_id=study_space_id,
        tenant_id=tenant_id,
    )
    chunks = await load_route_source_chunks(
        session=session,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
    )
    version = await next_route_version(session=session, study_space_id=study_space_id)
    route, chapters = await persist_generated_route(
        session=session,
        study_space=study_space,
        version=version,
        chunks=chunks,
        generator=generator,
        max_chapters=max_chapters,
    )
    await session.commit()
    return route, chapters


async def list_routes_for_space(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> list[tuple[LearningRoute, list[Chapter]]]:
    await ensure_study_space_in_tenant(
        session=session,
        study_space_id=study_space_id,
        tenant_id=tenant_id,
    )
    route_rows = await session.scalars(
        select(LearningRoute)
        .where(
            LearningRoute.tenant_id == tenant_id,
            LearningRoute.study_space_id == study_space_id,
        )
        .order_by(LearningRoute.created_at.desc(), LearningRoute.version.desc())
    )
    routes = list(route_rows)
    if not routes:
        return []

    chapter_rows = await session.scalars(
        select(Chapter)
        .where(Chapter.learning_route_id.in_([route.id for route in routes]))
        .order_by(Chapter.order_index)
    )
    chapters_by_route: dict[uuid.UUID, list[Chapter]] = {route.id: [] for route in routes}
    for chapter in chapter_rows:
        chapters_by_route.setdefault(chapter.learning_route_id, []).append(chapter)
    return [(route, chapters_by_route.get(route.id, [])) for route in routes]


async def list_active_chapters(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    study_space_id: uuid.UUID,
) -> list[Chapter]:
    await ensure_study_space_in_tenant(
        session=session,
        study_space_id=study_space_id,
        tenant_id=tenant_id,
    )
    active_route = await session.scalar(
        select(LearningRoute).where(
            LearningRoute.tenant_id == tenant_id,
            LearningRoute.study_space_id == study_space_id,
            LearningRoute.status == LearningRouteStatus.active,
        )
    )
    if active_route is None:
        return []
    rows = await session.scalars(
        select(Chapter)
        .where(Chapter.learning_route_id == active_route.id)
        .order_by(Chapter.order_index)
    )
    return list(rows)


async def activate_route(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    route_id: uuid.UUID,
) -> tuple[LearningRoute, list[Chapter]]:
    route = await session.scalar(
        select(LearningRoute).where(
            LearningRoute.id == route_id,
            LearningRoute.tenant_id == tenant_id,
        )
    )
    if route is None:
        raise ValueError("Route not found for tenant")
    if route.status == LearningRouteStatus.archived:
        raise ValueError("Archived routes cannot be activated")

    active_routes = await session.scalars(
        select(LearningRoute).where(
            LearningRoute.tenant_id == tenant_id,
            LearningRoute.study_space_id == route.study_space_id,
            LearningRoute.status == LearningRouteStatus.active,
        )
    )
    for active_route in active_routes:
        if active_route.id != route.id:
            active_route.status = LearningRouteStatus.archived

    route.status = LearningRouteStatus.active
    route.activated_at = datetime.now(UTC)

    chapter_rows = await session.scalars(
        select(Chapter)
        .where(Chapter.learning_route_id == route.id)
        .order_by(Chapter.order_index)
    )
    chapters = list(chapter_rows)
    for index, chapter in enumerate(chapters):
        if chapter.status != ChapterStatus.completed:
            chapter.status = ChapterStatus.active if index == 0 else ChapterStatus.not_started

    study_space = await session.scalar(
        select(StudySpace).where(
            StudySpace.id == route.study_space_id,
            StudySpace.tenant_id == tenant_id,
        )
    )
    if study_space is not None:
        study_space.route_outline = build_route_outline(chapters)

    await session.commit()
    return route, chapters


def build_route_outline(chapters: list[Chapter]) -> list[dict]:
    return [
        {
            "order": chapter.order_index,
            "title": chapter.title,
            "description": chapter.summary,
            "estimated_days": chapter.estimated_days,
        }
        for chapter in chapters
    ]
```

- [ ] **Step 5: Run service tests**

Run:

```powershell
python -m pytest tests/test_learning_route_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/domain/learning_routes/schemas.py apps/api/app/domain/learning_routes/service.py apps/api/tests/test_learning_route_service.py
git commit -m "feat: add learning route service"
```

---

### Task 4: Add Learning Route API Routes

**Files:**
- Create: `apps/api/app/api/routes_learning_routes.py`
- Modify: `apps/api/app/api/router.py`
- Create: `apps/api/tests/test_learning_route_routes.py`

- [ ] **Step 1: Write route tests**

Create `apps/api/tests/test_learning_route_routes.py`:

```python
import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api import routes_learning_routes
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.main import app


def fake_route(study_space_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000301"),
        study_space_id=study_space_id,
        version=1,
        status=SimpleNamespace(value="draft"),
        title="Route",
        summary="Summary",
        generation_strategy="deterministic",
        created_at=None,
        activated_at=None,
    )


def fake_chapter(route_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000401"),
        learning_route_id=route_id,
        order_index=1,
        title="Intro",
        goal="Learn basics",
        summary="Start here",
        estimated_days=3,
        status=SimpleNamespace(value="not_started"),
        source_chunk_refs=[],
    )


async def fake_get_db_session() -> AsyncGenerator[object, None]:
    yield object()


async def test_create_route_draft_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_create_route_draft(**kwargs):
        captured.update(kwargs)
        route = fake_route(study_space_id)
        return route, [fake_chapter(route.id)]

    monkeypatch.setattr(routes_learning_routes, "create_route_draft", fake_create_route_draft)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/study-spaces/{study_space_id}/route-drafts",
                json={"max_chapters": 4},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["route"]["status"] == "draft"
    assert captured["tenant_id"] == tenant_id
    assert captured["study_space_id"] == study_space_id
    assert captured["max_chapters"] == 4


async def test_activate_route_maps_missing_route_to_404(monkeypatch) -> None:
    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_activate_route(**kwargs):
        raise ValueError("Route not found for tenant")

    monkeypatch.setattr(routes_learning_routes, "activate_route", fake_activate_route)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/routes/{uuid.uuid4()}/activate")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Route not found for tenant"}
```

- [ ] **Step 2: Run route tests to verify failure**

Run:

```powershell
python -m pytest tests/test_learning_route_routes.py -q
```

Expected: FAIL because route module does not exist.

- [ ] **Step 3: Add API route module**

Create `apps/api/app/api/routes_learning_routes.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.learning_routes.generator import DeterministicRouteGenerator
from app.domain.learning_routes.schemas import (
    ChapterResponse,
    ChaptersListResponse,
    LearningRouteResponse,
    RouteDraftRequest,
    RoutesListResponse,
    RouteWithChaptersResponse,
)
from app.domain.learning_routes.service import (
    activate_route,
    create_route_draft,
    list_active_chapters,
    list_routes_for_space,
)

router = APIRouter(tags=["learning-routes"])


def route_response(route) -> LearningRouteResponse:
    return LearningRouteResponse(
        id=route.id,
        study_space_id=route.study_space_id,
        version=route.version,
        status=route.status.value,
        title=route.title,
        summary=route.summary,
        generation_strategy=route.generation_strategy,
        created_at=route.created_at,
        activated_at=route.activated_at,
    )


def chapter_response(chapter) -> ChapterResponse:
    return ChapterResponse(
        id=chapter.id,
        learning_route_id=chapter.learning_route_id,
        order_index=chapter.order_index,
        title=chapter.title,
        goal=chapter.goal,
        summary=chapter.summary,
        estimated_days=chapter.estimated_days,
        status=chapter.status.value,
        source_chunk_refs=chapter.source_chunk_refs,
    )


@router.post(
    "/study-spaces/{study_space_id}/route-drafts",
    response_model=RouteWithChaptersResponse,
    status_code=201,
)
async def create_study_space_route_draft(
    study_space_id: uuid.UUID,
    payload: RouteDraftRequest | None = None,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> RouteWithChaptersResponse:
    request = payload or RouteDraftRequest()
    try:
        route, chapters = await create_route_draft(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
            generator=DeterministicRouteGenerator(),
            max_chapters=request.max_chapters,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return RouteWithChaptersResponse(
        route=route_response(route),
        chapters=[chapter_response(chapter) for chapter in chapters],
    )


@router.get("/study-spaces/{study_space_id}/routes", response_model=RoutesListResponse)
async def get_study_space_routes(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> RoutesListResponse:
    try:
        routes = await list_routes_for_space(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RoutesListResponse(
        routes=[
            RouteWithChaptersResponse(
                route=route_response(route),
                chapters=[chapter_response(chapter) for chapter in chapters],
            )
            for route, chapters in routes
        ]
    )


@router.get("/study-spaces/{study_space_id}/chapters", response_model=ChaptersListResponse)
async def get_active_chapters(
    study_space_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChaptersListResponse:
    try:
        chapters = await list_active_chapters(
            session=session,
            tenant_id=context.tenant_id,
            study_space_id=study_space_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChaptersListResponse(chapters=[chapter_response(chapter) for chapter in chapters])


@router.post("/routes/{route_id}/activate", response_model=RouteWithChaptersResponse)
async def activate_learning_route(
    route_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> RouteWithChaptersResponse:
    try:
        route, chapters = await activate_route(
            session=session,
            tenant_id=context.tenant_id,
            route_id=route_id,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Route not found for tenant" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return RouteWithChaptersResponse(
        route=route_response(route),
        chapters=[chapter_response(chapter) for chapter in chapters],
    )
```

- [ ] **Step 4: Register route module**

Modify `apps/api/app/api/router.py`:

```python
from app.api import (
    routes_health,
    routes_ingestion,
    routes_learning_routes,
    routes_retrieval,
    routes_sources,
    routes_study_spaces,
    routes_uploads,
)
...
api_router.include_router(routes_learning_routes.router)
```

- [ ] **Step 5: Run route tests**

Run:

```powershell
python -m pytest tests/test_learning_route_routes.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/api/routes_learning_routes.py apps/api/app/api/router.py apps/api/tests/test_learning_route_routes.py
git commit -m "feat: add learning route api"
```

---

### Task 5: Add Frontend Route Panel

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Modify: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Add frontend route panel tests**

Append to `apps/web/tests/source-library.spec.ts` inside the existing `describe` block:

```ts
  it('renders route empty state and generates a draft route', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/route-drafts')) {
        return Promise.resolve({
          route: routeItem({ status: 'draft' }),
          chapters: [chapterItem()]
        })
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('No learning route yet.')

    await wrapper.find('[data-testid="generate-route"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces/00000000-0000-0000-0000-000000000101/route-drafts',
      expect.objectContaining({ method: 'POST' })
    )
    expect(wrapper.text()).toContain('Draft route')
    expect(wrapper.text()).toContain('Intro chapter')
  })

  it('activates a draft route from the route panel', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({
          routes: [
            {
              route: routeItem({ status: 'draft' }),
              chapters: [chapterItem()]
            }
          ]
        })
      }
      if (url.endsWith('/routes/00000000-0000-0000-0000-000000000501/activate')) {
        return Promise.resolve({
          route: routeItem({ status: 'active' }),
          chapters: [chapterItem({ status: 'active' })]
        })
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="activate-route"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/routes/00000000-0000-0000-0000-000000000501/activate',
      expect.objectContaining({ method: 'POST' })
    )
    expect(wrapper.text()).toContain('Active route')
  })
```

Add helpers near existing source helpers:

```ts
function routeItem(overrides = {}) {
  return {
    id: '00000000-0000-0000-0000-000000000501',
    study_space_id: '00000000-0000-0000-0000-000000000101',
    version: 1,
    status: 'draft',
    title: 'Draft route',
    summary: 'A generated route.',
    generation_strategy: 'deterministic',
    created_at: null,
    activated_at: null,
    ...overrides
  }
}

function chapterItem(overrides = {}) {
  return {
    id: '00000000-0000-0000-0000-000000000601',
    learning_route_id: '00000000-0000-0000-0000-000000000501',
    order_index: 1,
    title: 'Intro chapter',
    goal: 'Learn the foundations.',
    summary: 'Start with the basics.',
    estimated_days: 3,
    status: 'not_started',
    source_chunk_refs: [],
    ...overrides
  }
}
```

- [ ] **Step 2: Run frontend tests to verify failure**

Run:

```powershell
cd apps\web
npm run test -- tests/source-library.spec.ts
```

Expected: FAIL because route panel API state does not exist.

- [ ] **Step 3: Add route types and state**

Modify `apps/web/pages/spaces/[id]/index.vue`.

Add interfaces after chunk interfaces:

```ts
interface LearningRoute {
  id: string
  study_space_id: string
  version: number
  status: 'draft' | 'active' | 'archived' | string
  title: string
  summary: string
  generation_strategy: string
  created_at: string | null
  activated_at: string | null
}

interface RouteChapter {
  id: string
  learning_route_id: string
  order_index: number
  title: string
  goal: string
  summary: string
  estimated_days: number
  status: string
  source_chunk_refs: Array<Record<string, unknown>>
}

interface RouteWithChapters {
  route: LearningRoute
  chapters: RouteChapter[]
}

interface RoutesListResponse {
  routes: RouteWithChapters[]
}
```

Add state after existing source/chunk state:

```ts
const routes = ref<RouteWithChapters[]>([])
const loadingRoutes = ref(false)
const generatingRoute = ref(false)
const activatingRouteId = ref<string | null>(null)
```

Add computed values:

```ts
const activeRoute = computed(() => routes.value.find(item => item.route.status === 'active') ?? null)
const latestDraftRoute = computed(() => routes.value.find(item => item.route.status === 'draft') ?? null)
const visibleRoute = computed(() => activeRoute.value ?? latestDraftRoute.value ?? null)
```

- [ ] **Step 4: Add route API helpers**

Add functions before `onMounted`:

```ts
async function loadRoutes() {
  loadingRoutes.value = true
  errorMessage.value = ''
  try {
    const response = await $fetch<RoutesListResponse>(
      `${config.public.apiBaseUrl}/study-spaces/${spaceId.value}/routes`,
      { headers: protectedHeaders() }
    )
    routes.value = response.routes
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to load learning routes.', error)
  } finally {
    loadingRoutes.value = false
  }
}

async function generateRouteDraft() {
  generatingRoute.value = true
  errorMessage.value = ''
  try {
    const response = await $fetch<RouteWithChapters>(
      `${config.public.apiBaseUrl}/study-spaces/${spaceId.value}/route-drafts`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { max_chapters: 5 }
      }
    )
    routes.value = [response, ...routes.value.filter(item => item.route.id !== response.route.id)]
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to generate learning route.', error)
  } finally {
    generatingRoute.value = false
  }
}

async function activateRoute(routeId: string) {
  activatingRouteId.value = routeId
  errorMessage.value = ''
  try {
    const response = await $fetch<RouteWithChapters>(
      `${config.public.apiBaseUrl}/routes/${routeId}/activate`,
      {
        method: 'POST',
        headers: protectedHeaders()
      }
    )
    routes.value = [
      response,
      ...routes.value
        .filter(item => item.route.id !== routeId)
        .map(item => ({
          ...item,
          route: item.route.status === 'active' ? { ...item.route, status: 'archived' } : item.route
        }))
    ]
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to activate learning route.', error)
  } finally {
    activatingRouteId.value = null
  }
}
```

Update `onMounted`:

```ts
onMounted(() => {
  loadSources()
  loadRoutes()
})
```

- [ ] **Step 5: Replace route overview template**

Find the current `route-overview` section and replace with:

```vue
        <section class="card route-overview">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Learning route</p>
              <h2>{{ visibleRoute?.route.status === 'active' ? 'Active route' : visibleRoute ? 'Draft route' : 'No learning route yet.' }}</h2>
              <p v-if="visibleRoute">{{ visibleRoute.route.summary }}</p>
              <p v-else>Generate a route from your goal and ingested source chunks.</p>
            </div>
            <div class="route-actions">
              <button
                data-testid="generate-route"
                type="button"
                class="secondary-button"
                :disabled="generatingRoute"
                @click="generateRouteDraft"
              >
                {{ generatingRoute ? 'Generating...' : visibleRoute ? 'Regenerate draft' : 'Generate route' }}
              </button>
              <button
                v-if="latestDraftRoute"
                data-testid="activate-route"
                type="button"
                class="primary-button"
                :disabled="activatingRouteId === latestDraftRoute.route.id"
                @click="activateRoute(latestDraftRoute.route.id)"
              >
                {{ activatingRouteId === latestDraftRoute.route.id ? 'Activating...' : 'Activate route' }}
              </button>
            </div>
          </div>

          <p v-if="loadingRoutes" class="muted">Loading learning routes...</p>
          <div v-else-if="visibleRoute" class="chapter-list">
            <article v-for="chapter in visibleRoute.chapters" :key="chapter.id" class="chapter-row">
              <span class="status-badge">{{ chapter.status }}</span>
              <div>
                <h3>{{ chapter.order_index }}. {{ chapter.title }}</h3>
                <p>{{ chapter.goal }}</p>
                <small>{{ chapter.estimated_days }} days</small>
              </div>
            </article>
          </div>
          <p v-else class="empty-state">No learning route yet. Generate a route after uploading or ingesting sources.</p>
        </section>
```

- [ ] **Step 6: Add route panel styles**

Add to scoped styles:

```css
.route-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.chapter-list {
  display: grid;
  gap: 12px;
}

.chapter-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  padding: 12px;
}

.chapter-row h3,
.chapter-row p {
  overflow-wrap: anywhere;
}

.chapter-row p {
  color: var(--color-muted);
}

.chapter-row small {
  color: var(--color-primary);
  font-weight: 800;
}
```

Inside the `@media (max-width: 1120px)` block, add:

```css
  .route-actions,
  .chapter-row {
    grid-template-columns: 1fr;
  }
```

- [ ] **Step 7: Run frontend tests**

Run:

```powershell
npm run test -- tests/source-library.spec.ts
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add apps/web/pages/spaces/[id]/index.vue apps/web/tests/source-library.spec.ts
git commit -m "feat: add route panel to study space"
```

---

### Task 6: Final Verification

**Files:**
- Read all files changed above.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
cd F:\AIproject\study_agent\apps\api
$env:PYTHONPATH = "$PWD"
python -m pytest -q
```

Expected:

- All non-guarded tests pass.
- Guarded Postgres integration tests remain skipped unless `RUN_POSTGRES_TESTS=1`.

- [ ] **Step 2: Run backend lint**

Run:

```powershell
python -m ruff check .
```

Expected: PASS.

- [ ] **Step 3: Check Alembic history**

Run:

```powershell
python -m alembic history
```

Expected: includes `0003_learning_routes`.

- [ ] **Step 4: Run frontend tests**

Run:

```powershell
cd F:\AIproject\study_agent\apps\web
npm run test
npm run typecheck
npm run build
```

Expected:

- Vitest passes.
- Typecheck exits 0, allowing existing Vue language plugin warning if no type errors.
- Build exits 0, allowing existing Nuxt sourcemap/deprecation warnings.

- [ ] **Step 5: Validate Docker Compose**

Run from repo root:

```powershell
docker compose -f infra/docker-compose.yml config
```

Expected: exit code 0. Docker credential warnings can be recorded as environment-only if config prints successfully.

## Final Verification

Before PR or merge, record:

```powershell
cd apps\api
$env:PYTHONPATH = "$PWD"
python -m pytest -q
python -m ruff check .
python -m alembic history
cd ..\web
npm run test
npm run typecheck
npm run build
cd ..\..
docker compose -f infra/docker-compose.yml config
```

## Execution Order

1. Create or use a feature branch/worktree such as `codex/route-generation-foundation`.
2. Execute Tasks 1-6 in order.
3. Keep commits small and reviewable.
4. Preserve existing untracked Chinese docs and package-lock line-ending noise unless explicitly asked.
5. Push branch and create PR after verification.

## Self-Review

- Spec coverage: Plan covers persistence, generator interface, deterministic generation, tenant-safe APIs, activation, frontend panel, and tests.
- Scope control: No LLM, LangGraph, route editing, chapter study page, chat, quiz, or background worker is included.
- Type consistency: Model names, enum values, API paths, and frontend response shapes match the design spec.
- Risk control: Backend domain is separated into `learning_routes`, and frontend changes are limited to the existing study-space detail page.
