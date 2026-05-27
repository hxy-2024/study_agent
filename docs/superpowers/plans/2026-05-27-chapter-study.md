# Chapter Study Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tenant-safe chapter study page where users can read chapter detail, inspect source evidence, complete a chapter, and move to the next chapter.

**Architecture:** Add a focused `chapter_study` backend domain for chapter detail and completion workflows, with FastAPI routes that derive tenant scope from auth context. Add a Nuxt chapter page and a `Study` action from the existing study-space route panel, keeping AI mentor UI reserved but non-functional in this phase.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.x async, pytest, httpx ASGI tests, Nuxt 4, Vue 3, TypeScript, Vitest, Vue Test Utils.

---

## Scope Check

This plan implements:

`docs/superpowers/specs/2026-05-27-chapter-study-design.md`

Execution base:

- `main` after PR #5 `Add route generation foundation` is merged.
- Existing files from route generation should be present:
  - `apps/api/app/db/models.py` with `Chapter`, `ChapterStatus`, `LearningRoute`, `LearningRouteStatus`.
  - `apps/api/app/api/routes_learning_routes.py`.
  - `apps/web/pages/spaces/[id]/index.vue` with route panel state.
  - `apps/web/tests/source-library.spec.ts` with route panel tests.

In scope:

- `GET /api/v1/chapters/{chapter_id}`.
- `POST /api/v1/chapters/{chapter_id}/complete`.
- Tenant-safe chapter detail service.
- Source evidence excerpts from referenced chunks.
- Completion state transition and next chapter activation.
- Study-space route panel `Study` action.
- New chapter study page.
- Backend and frontend tests.

Out of scope:

- Real LLM calls.
- RAG generated answers.
- Tutor message persistence.
- Quiz, flashcards, spaced repetition, analytics, and background jobs.
- New database tables or migrations.

## File Structure

```text
apps/api/
  app/
    api/
      router.py
      routes_chapter_study.py
    domain/
      chapter_study/
        __init__.py
        schemas.py
        service.py
  tests/
    test_chapter_study_service.py
    test_chapter_study_routes.py

apps/web/
  pages/
    chapters/
      [id]/
        index.vue
    spaces/
      [id]/
        index.vue
  tests/
    chapter-study.spec.ts
    source-library.spec.ts
```

Responsibilities:

- `schemas.py`: Pydantic response DTOs for chapter detail and evidence.
- `service.py`: tenant-safe chapter lookup, evidence loading, next chapter detection, completion transition.
- `routes_chapter_study.py`: FastAPI route handlers and `ValueError` to HTTP error mapping.
- `pages/chapters/[id]/index.vue`: chapter study experience and reserved mentor panel.
- `pages/spaces/[id]/index.vue`: add `Study` navigation action to chapter rows.
- Tests verify service behavior, route auth boundaries, and frontend interactions.

---

### Task 1: Add Chapter Study Service Tests

**Files:**
- Create: `apps/api/tests/test_chapter_study_service.py`

- [ ] **Step 1: Write failing service tests**

Create `apps/api/tests/test_chapter_study_service.py`:

```python
import uuid
from types import SimpleNamespace

import pytest

from app.db.models import ChapterStatus, LearningRouteStatus
from app.domain.chapter_study.service import (
    build_chapter_detail,
    chapter_response,
    complete_chapter,
    evidence_response,
    find_next_chapter,
)


def make_chapter(order_index: int, status: ChapterStatus = ChapterStatus.not_started):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        learning_route_id=uuid.uuid4(),
        order_index=order_index,
        title=f"Chapter {order_index}",
        goal="Learn the concept.",
        summary="Study the core material.",
        estimated_days=3,
        status=status,
        source_chunk_refs=[],
    )


def test_chapter_response_maps_model() -> None:
    chapter = make_chapter(order_index=1, status=ChapterStatus.active)

    response = chapter_response(chapter)

    assert response.id == chapter.id
    assert response.status == "active"
    assert response.order_index == 1


def test_evidence_response_truncates_text() -> None:
    source = SimpleNamespace(id=uuid.uuid4(), filename="notes.md")
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        source_id=source.id,
        chunk_index=0,
        text="x" * 800,
        citation={"page_number": 2},
    )

    response = evidence_response(chunk=chunk, source=source, max_chars=700)

    assert response.source_filename == "notes.md"
    assert response.chunk_index == 0
    assert len(response.text) == 700
    assert response.citation == {"page_number": 2}


def test_find_next_chapter_uses_lowest_incomplete_after_current() -> None:
    current = make_chapter(order_index=1, status=ChapterStatus.active)
    completed = make_chapter(order_index=2, status=ChapterStatus.completed)
    next_chapter = make_chapter(order_index=3, status=ChapterStatus.not_started)
    later = make_chapter(order_index=4, status=ChapterStatus.not_started)

    assert find_next_chapter(current, [later, completed, next_chapter]) == next_chapter


def test_build_chapter_detail_returns_next_chapter_id() -> None:
    current = make_chapter(order_index=1, status=ChapterStatus.active)
    next_chapter = make_chapter(order_index=2, status=ChapterStatus.not_started)
    route = SimpleNamespace(
        id=current.learning_route_id,
        study_space_id=current.study_space_id,
        version=1,
        status=LearningRouteStatus.active,
        title="Route",
    )
    study_space = SimpleNamespace(id=current.study_space_id, name="Linear Algebra")

    detail = build_chapter_detail(
        chapter=current,
        route=route,
        study_space=study_space,
        evidence=[],
        route_chapters=[current, next_chapter],
    )

    assert detail.chapter.id == current.id
    assert detail.route.title == "Route"
    assert detail.study_space.name == "Linear Algebra"
    assert detail.next_chapter_id == next_chapter.id


@pytest.mark.anyio
async def test_complete_chapter_is_idempotent_when_already_completed(monkeypatch) -> None:
    chapter = make_chapter(order_index=1, status=ChapterStatus.completed)
    route = SimpleNamespace(
        id=chapter.learning_route_id,
        study_space_id=chapter.study_space_id,
        version=1,
        status=LearningRouteStatus.active,
        title="Route",
    )
    study_space = SimpleNamespace(id=chapter.study_space_id, name="Linear Algebra")

    async def fake_load_chapter_context(**kwargs):
        return chapter, route, study_space, [chapter], []

    monkeypatch.setattr("app.domain.chapter_study.service.load_chapter_context", fake_load_chapter_context)

    class FakeSession:
        committed = False

        async def commit(self) -> None:
            self.committed = True

    detail = await complete_chapter(
        session=FakeSession(),
        tenant_id=chapter.tenant_id,
        chapter_id=chapter.id,
    )

    assert detail.chapter.status == "completed"
    assert detail.next_chapter_id is None


@pytest.mark.anyio
async def test_complete_chapter_activates_next_incomplete(monkeypatch) -> None:
    current = make_chapter(order_index=1, status=ChapterStatus.active)
    next_chapter = make_chapter(order_index=2, status=ChapterStatus.not_started)
    next_chapter.tenant_id = current.tenant_id
    next_chapter.study_space_id = current.study_space_id
    next_chapter.learning_route_id = current.learning_route_id
    route = SimpleNamespace(
        id=current.learning_route_id,
        study_space_id=current.study_space_id,
        version=1,
        status=LearningRouteStatus.active,
        title="Route",
    )
    study_space = SimpleNamespace(id=current.study_space_id, name="Linear Algebra")

    async def fake_load_chapter_context(**kwargs):
        return current, route, study_space, [current, next_chapter], []

    monkeypatch.setattr("app.domain.chapter_study.service.load_chapter_context", fake_load_chapter_context)

    class FakeSession:
        async def commit(self) -> None:
            return None

    detail = await complete_chapter(
        session=FakeSession(),
        tenant_id=current.tenant_id,
        chapter_id=current.id,
    )

    assert current.status == ChapterStatus.completed
    assert next_chapter.status == ChapterStatus.active
    assert detail.chapter.status == "completed"
    assert detail.next_chapter_id == next_chapter.id
```

- [ ] **Step 2: Run tests to verify failure**

Run from `apps/api`:

```powershell
$env:PYTHONPATH = "$PWD"
python -m pytest tests/test_chapter_study_service.py -q
```

Expected: FAIL because `app.domain.chapter_study` does not exist.

- [ ] **Step 3: Commit failing tests only if your workflow requires red commits**

Default: do not commit the red state. Continue to Task 2.

---

### Task 2: Add Chapter Study Schemas and Service

**Files:**
- Create: `apps/api/app/domain/chapter_study/__init__.py`
- Create: `apps/api/app/domain/chapter_study/schemas.py`
- Create: `apps/api/app/domain/chapter_study/service.py`

- [ ] **Step 1: Add schema module**

Create `apps/api/app/domain/chapter_study/__init__.py`:

```python
"""Chapter study domain."""
```

Create `apps/api/app/domain/chapter_study/schemas.py`:

```python
import uuid

from pydantic import BaseModel


class ChapterStudyChapterResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    learning_route_id: uuid.UUID
    order_index: int
    title: str
    goal: str
    summary: str
    estimated_days: int
    status: str
    source_chunk_refs: list[dict]


class ChapterStudyRouteResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    version: int
    status: str
    title: str


class ChapterStudySpaceResponse(BaseModel):
    id: uuid.UUID
    name: str


class ChapterEvidenceResponse(BaseModel):
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    source_filename: str
    text: str
    citation: dict


class ChapterStudyDetailResponse(BaseModel):
    chapter: ChapterStudyChapterResponse
    route: ChapterStudyRouteResponse
    study_space: ChapterStudySpaceResponse
    evidence: list[ChapterEvidenceResponse]
    next_chapter_id: uuid.UUID | None = None
```

- [ ] **Step 2: Add service module**

Create `apps/api/app/domain/chapter_study/service.py`:

```python
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Chapter,
    ChapterStatus,
    LearningRoute,
    Source,
    SourceChunk,
    StudySpace,
)
from app.domain.chapter_study.schemas import (
    ChapterEvidenceResponse,
    ChapterStudyChapterResponse,
    ChapterStudyDetailResponse,
    ChapterStudyRouteResponse,
    ChapterStudySpaceResponse,
)


def chapter_response(chapter) -> ChapterStudyChapterResponse:
    return ChapterStudyChapterResponse(
        id=chapter.id,
        study_space_id=chapter.study_space_id,
        learning_route_id=chapter.learning_route_id,
        order_index=chapter.order_index,
        title=chapter.title,
        goal=chapter.goal,
        summary=chapter.summary,
        estimated_days=chapter.estimated_days,
        status=chapter.status.value,
        source_chunk_refs=chapter.source_chunk_refs,
    )


def route_response(route) -> ChapterStudyRouteResponse:
    return ChapterStudyRouteResponse(
        id=route.id,
        study_space_id=route.study_space_id,
        version=route.version,
        status=route.status.value,
        title=route.title,
    )


def study_space_response(study_space) -> ChapterStudySpaceResponse:
    return ChapterStudySpaceResponse(id=study_space.id, name=study_space.name)


def evidence_response(chunk, source, max_chars: int = 700) -> ChapterEvidenceResponse:
    return ChapterEvidenceResponse(
        source_id=chunk.source_id,
        chunk_id=chunk.id,
        chunk_index=chunk.chunk_index,
        source_filename=source.filename,
        text=chunk.text[:max_chars],
        citation=chunk.citation,
    )


def referenced_chunk_ids(source_chunk_refs: Iterable[dict]) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    for ref in source_chunk_refs:
        raw_id = ref.get("chunk_id")
        if raw_id is None:
            continue
        try:
            ids.append(uuid.UUID(str(raw_id)))
        except ValueError:
            continue
    return ids


def find_next_chapter(chapter, route_chapters: list) -> object | None:
    candidates = [
        candidate
        for candidate in route_chapters
        if candidate.order_index > chapter.order_index and candidate.status != ChapterStatus.completed
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.order_index)[0]


def build_chapter_detail(
    chapter,
    route,
    study_space,
    evidence: list[ChapterEvidenceResponse],
    route_chapters: list,
) -> ChapterStudyDetailResponse:
    next_chapter = find_next_chapter(chapter, route_chapters)
    return ChapterStudyDetailResponse(
        chapter=chapter_response(chapter),
        route=route_response(route),
        study_space=study_space_response(study_space),
        evidence=evidence,
        next_chapter_id=getattr(next_chapter, "id", None),
    )


async def load_chapter_context(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> tuple[Chapter, LearningRoute, StudySpace, list[Chapter], list[ChapterEvidenceResponse]]:
    chapter = await session.scalar(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.tenant_id == tenant_id,
        )
    )
    if chapter is None:
        raise ValueError("Chapter not found for tenant")

    route = await session.scalar(
        select(LearningRoute).where(
            LearningRoute.id == chapter.learning_route_id,
            LearningRoute.tenant_id == tenant_id,
        )
    )
    if route is None:
        raise ValueError("Route not found for tenant")

    study_space = await session.scalar(
        select(StudySpace).where(
            StudySpace.id == chapter.study_space_id,
            StudySpace.tenant_id == tenant_id,
        )
    )
    if study_space is None:
        raise ValueError("Study space not found for tenant")

    route_chapters_rows = await session.scalars(
        select(Chapter)
        .where(
            Chapter.tenant_id == tenant_id,
            Chapter.learning_route_id == chapter.learning_route_id,
        )
        .order_by(Chapter.order_index)
    )
    route_chapters = list(route_chapters_rows)
    evidence = await load_chapter_evidence(session=session, tenant_id=tenant_id, chapter=chapter)
    return chapter, route, study_space, route_chapters, evidence


async def load_chapter_evidence(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter: Chapter,
) -> list[ChapterEvidenceResponse]:
    chunk_ids = referenced_chunk_ids(chapter.source_chunk_refs)
    if not chunk_ids:
        return []

    rows = await session.execute(
        select(SourceChunk, Source)
        .join(Source, Source.id == SourceChunk.source_id)
        .where(
            SourceChunk.id.in_(chunk_ids),
            SourceChunk.tenant_id == tenant_id,
            SourceChunk.study_space_id == chapter.study_space_id,
            SourceChunk.is_active.is_(True),
            Source.tenant_id == tenant_id,
            Source.study_space_id == chapter.study_space_id,
        )
        .order_by(SourceChunk.chunk_index)
    )
    return [evidence_response(chunk=chunk, source=source) for chunk, source in rows.all()]


async def get_chapter_detail(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> ChapterStudyDetailResponse:
    chapter, route, study_space, route_chapters, evidence = await load_chapter_context(
        session=session,
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )
    return build_chapter_detail(
        chapter=chapter,
        route=route,
        study_space=study_space,
        evidence=evidence,
        route_chapters=route_chapters,
    )


async def complete_chapter(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> ChapterStudyDetailResponse:
    chapter, route, study_space, route_chapters, evidence = await load_chapter_context(
        session=session,
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )
    if chapter.status != ChapterStatus.completed:
        chapter.status = ChapterStatus.completed
        next_chapter = find_next_chapter(chapter, route_chapters)
        if next_chapter is not None:
            next_chapter.status = ChapterStatus.active
        await session.commit()

    return build_chapter_detail(
        chapter=chapter,
        route=route,
        study_space=study_space,
        evidence=evidence,
        route_chapters=route_chapters,
    )
```

- [ ] **Step 3: Run service tests**

Run:

```powershell
$env:PYTHONPATH = "$PWD"
python -m pytest tests/test_chapter_study_service.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add apps/api/app/domain/chapter_study apps/api/tests/test_chapter_study_service.py
git commit -m "feat: add chapter study service"
```

---

### Task 3: Add Chapter Study API Routes

**Files:**
- Create: `apps/api/app/api/routes_chapter_study.py`
- Modify: `apps/api/app/api/router.py`
- Create: `apps/api/tests/test_chapter_study_routes.py`

- [ ] **Step 1: Write failing API route tests**

Create `apps/api/tests/test_chapter_study_routes.py`:

```python
import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient

from app.api import routes_chapter_study
from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.chapter_study.schemas import (
    ChapterStudyChapterResponse,
    ChapterStudyDetailResponse,
    ChapterStudyRouteResponse,
    ChapterStudySpaceResponse,
)
from app.main import app


async def fake_get_db_session() -> AsyncGenerator[object, None]:
    yield object()


def detail_fixture(chapter_id: uuid.UUID) -> ChapterStudyDetailResponse:
    study_space_id = uuid.uuid4()
    route_id = uuid.uuid4()
    return ChapterStudyDetailResponse(
        chapter=ChapterStudyChapterResponse(
            id=chapter_id,
            study_space_id=study_space_id,
            learning_route_id=route_id,
            order_index=1,
            title="Intro",
            goal="Learn basics",
            summary="Start here",
            estimated_days=3,
            status="active",
            source_chunk_refs=[],
        ),
        route=ChapterStudyRouteResponse(
            id=route_id,
            study_space_id=study_space_id,
            version=1,
            status="active",
            title="Route",
        ),
        study_space=ChapterStudySpaceResponse(id=study_space_id, name="Linear Algebra"),
        evidence=[],
        next_chapter_id=None,
    )


async def test_get_chapter_detail_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_get_chapter_detail(**kwargs):
        captured.update(kwargs)
        return detail_fixture(chapter_id)

    monkeypatch.setattr(routes_chapter_study, "get_chapter_detail", fake_get_chapter_detail)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/chapters/{chapter_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["chapter"]["title"] == "Intro"
    assert captured["tenant_id"] == tenant_id
    assert captured["chapter_id"] == chapter_id


async def test_complete_chapter_uses_authorized_tenant(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    captured = {}

    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=tenant_id)

    async def fake_complete_chapter(**kwargs):
        captured.update(kwargs)
        detail = detail_fixture(chapter_id)
        detail.chapter.status = "completed"
        return detail

    monkeypatch.setattr(routes_chapter_study, "complete_chapter", fake_complete_chapter)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/chapters/{chapter_id}/complete")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["chapter"]["status"] == "completed"
    assert captured["tenant_id"] == tenant_id


async def test_missing_chapter_maps_to_404(monkeypatch) -> None:
    async def fake_context() -> CurrentUserContext:
        return CurrentUserContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    async def fake_get_chapter_detail(**kwargs):
        raise ValueError("Chapter not found for tenant")

    monkeypatch.setattr(routes_chapter_study, "get_chapter_detail", fake_get_chapter_detail)
    app.dependency_overrides[get_db_session] = fake_get_db_session
    app.dependency_overrides[get_authorized_user_context] = fake_context
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/chapters/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Chapter not found for tenant"}
```

- [ ] **Step 2: Run route tests to verify failure**

Run:

```powershell
$env:PYTHONPATH = "$PWD"
python -m pytest tests/test_chapter_study_routes.py -q
```

Expected: FAIL because `routes_chapter_study` is not registered or does not exist.

- [ ] **Step 3: Add route module**

Create `apps/api/app/api/routes_chapter_study.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.chapter_study.schemas import ChapterStudyDetailResponse
from app.domain.chapter_study.service import complete_chapter, get_chapter_detail

router = APIRouter(tags=["chapter-study"])


def map_chapter_error(exc: ValueError) -> HTTPException:
    status_code = 404 if "not found" in str(exc).lower() else 400
    return HTTPException(status_code=status_code, detail=str(exc))


@router.get("/chapters/{chapter_id}", response_model=ChapterStudyDetailResponse)
async def read_chapter_detail(
    chapter_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterStudyDetailResponse:
    try:
        return await get_chapter_detail(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=chapter_id,
        )
    except ValueError as exc:
        raise map_chapter_error(exc) from exc


@router.post("/chapters/{chapter_id}/complete", response_model=ChapterStudyDetailResponse)
async def complete_chapter_route(
    chapter_id: uuid.UUID,
    context: CurrentUserContext = Depends(get_authorized_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterStudyDetailResponse:
    try:
        return await complete_chapter(
            session=session,
            tenant_id=context.tenant_id,
            chapter_id=chapter_id,
        )
    except ValueError as exc:
        raise map_chapter_error(exc) from exc
```

- [ ] **Step 4: Register router**

Modify `apps/api/app/api/router.py`:

```python
from app.api import (
    routes_chapter_study,
    routes_health,
    routes_ingestion,
    routes_learning_routes,
    routes_retrieval,
    routes_sources,
    routes_study_spaces,
    routes_uploads,
)
...
api_router.include_router(routes_chapter_study.router)
```

Place the include near the other feature routers:

```python
api_router.include_router(routes_health.router)
api_router.include_router(routes_chapter_study.router)
api_router.include_router(routes_ingestion.router)
```

- [ ] **Step 5: Run route tests**

Run:

```powershell
$env:PYTHONPATH = "$PWD"
python -m pytest tests/test_chapter_study_routes.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/api/routes_chapter_study.py apps/api/app/api/router.py apps/api/tests/test_chapter_study_routes.py
git commit -m "feat: add chapter study api"
```

---

### Task 4: Add Study Links to Route Panel

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Modify: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Add failing frontend test for Study link**

In `apps/web/tests/source-library.spec.ts`, update the route panel test that renders a draft route. After asserting `Intro chapter`, add:

```ts
    const studyLink = wrapper.find('[data-testid="study-chapter"]')
    expect(studyLink.exists()).toBe(true)
    expect(studyLink.attributes('to')).toBe('/chapters/00000000-0000-0000-0000-000000000601')
```

If the test environment stubs `NuxtLink` without exposing `to`, use the rendered HTML assertion:

```ts
    expect(wrapper.html()).toContain('/chapters/00000000-0000-0000-0000-000000000601')
```

- [ ] **Step 2: Run frontend route panel test to verify failure**

Run from `apps/web`:

```powershell
npm run test -- tests/source-library.spec.ts
```

Expected: FAIL because chapter rows do not render a study link yet.

- [ ] **Step 3: Add Study link to chapter rows**

Modify the chapter row in `apps/web/pages/spaces/[id]/index.vue`.

Find:

```vue
            <article v-for="chapter in visibleRoute.chapters" :key="chapter.id" class="chapter-row">
              <span class="status-badge">{{ chapter.status }}</span>
              <div>
                <h3>{{ chapter.order_index }}. {{ chapter.title }}</h3>
                <p>{{ chapter.goal }}</p>
                <small>{{ chapter.estimated_days }} days</small>
              </div>
            </article>
```

Replace with:

```vue
            <article v-for="chapter in visibleRoute.chapters" :key="chapter.id" class="chapter-row">
              <span class="status-badge">{{ chapter.status }}</span>
              <div>
                <h3>{{ chapter.order_index }}. {{ chapter.title }}</h3>
                <p>{{ chapter.goal }}</p>
                <small>{{ chapter.estimated_days }} days</small>
              </div>
              <NuxtLink
                data-testid="study-chapter"
                class="secondary-button chapter-study-link"
                :to="`/chapters/${chapter.id}`"
              >
                Study
              </NuxtLink>
            </article>
```

- [ ] **Step 4: Add link styles**

In the scoped styles of `apps/web/pages/spaces/[id]/index.vue`, add:

```css
.chapter-study-link {
  align-self: start;
  text-decoration: none;
}
```

Update `.chapter-row` desktop grid from:

```css
grid-template-columns: auto minmax(0, 1fr);
```

to:

```css
grid-template-columns: auto minmax(0, 1fr) auto;
```

The existing mobile media rule can keep `.chapter-row { grid-template-columns: 1fr; }`.

- [ ] **Step 5: Run frontend test**

Run:

```powershell
npm run test -- tests/source-library.spec.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/pages/spaces/[id]/index.vue apps/web/tests/source-library.spec.ts
git commit -m "feat: link route chapters to study page"
```

---

### Task 5: Add Chapter Study Page Tests and Page

**Files:**
- Create: `apps/web/pages/chapters/[id]/index.vue`
- Create: `apps/web/tests/chapter-study.spec.ts`

- [ ] **Step 1: Write failing chapter page tests**

Create `apps/web/tests/chapter-study.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()

vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRoute', () => ({
  params: {
    id: '00000000-0000-0000-0000-000000000601'
  }
}))

const { default: ChapterStudyPage } = await import('../pages/chapters/[id]/index.vue')

function mountPage() {
  return mount(ChapterStudyPage, {
    global: {
      stubs: {
        NuxtLink: true
      }
    }
  })
}

function chapterDetail(overrides = {}) {
  return {
    chapter: {
      id: '00000000-0000-0000-0000-000000000601',
      study_space_id: '00000000-0000-0000-0000-000000000101',
      learning_route_id: '00000000-0000-0000-0000-000000000501',
      order_index: 1,
      title: 'Intro chapter',
      goal: 'Learn the foundations.',
      summary: 'Start with the basics.',
      estimated_days: 3,
      status: 'active',
      source_chunk_refs: [],
      ...(overrides as { chapter?: Record<string, unknown> }).chapter
    },
    route: {
      id: '00000000-0000-0000-0000-000000000501',
      study_space_id: '00000000-0000-0000-0000-000000000101',
      version: 1,
      status: 'active',
      title: 'Draft route'
    },
    study_space: {
      id: '00000000-0000-0000-0000-000000000101',
      name: 'Linear Algebra'
    },
    evidence: [],
    next_chapter_id: null,
    ...overrides
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('ChapterStudyPage', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue(chapterDetail())
  })

  it('renders chapter details and reserved mentor panel', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Intro chapter')
    expect(wrapper.text()).toContain('Learn the foundations.')
    expect(wrapper.text()).toContain('Start with the basics.')
    expect(wrapper.text()).toContain('Draft route')
    expect(wrapper.text()).toContain('AI Mentor')
    expect(wrapper.find('textarea[disabled]').exists()).toBe(true)
  })

  it('renders source evidence cards', async () => {
    fetchMock.mockResolvedValueOnce(
      chapterDetail({
        evidence: [
          {
            source_id: '00000000-0000-0000-0000-000000000201',
            chunk_id: '00000000-0000-0000-0000-000000000301',
            chunk_index: 0,
            source_filename: 'notes.md',
            text: 'Embeddings convert text into vectors.',
            citation: { page_number: 2 }
          }
        ]
      })
    )

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('notes.md')
    expect(wrapper.text()).toContain('Embeddings convert text into vectors.')
    expect(wrapper.text()).toContain('Page 2')
  })

  it('renders empty evidence state', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('No source evidence is linked to this chapter yet.')
  })

  it('marks chapter complete and shows next chapter action', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/complete') && options?.method === 'POST') {
        return Promise.resolve(
          chapterDetail({
            chapter: { status: 'completed' },
            next_chapter_id: '00000000-0000-0000-0000-000000000602'
          })
        )
      }
      return Promise.resolve(chapterDetail())
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="complete-chapter"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/chapters/00000000-0000-0000-0000-000000000601/complete',
      expect.objectContaining({ method: 'POST' })
    )
    expect(wrapper.text()).toContain('completed')
    expect(wrapper.text()).toContain('Next chapter')
    expect(wrapper.html()).toContain('/chapters/00000000-0000-0000-0000-000000000602')
  })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
npm run test -- tests/chapter-study.spec.ts
```

Expected: FAIL because `pages/chapters/[id]/index.vue` does not exist.

- [ ] **Step 3: Create chapter study page**

Create `apps/web/pages/chapters/[id]/index.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

interface ChapterStudyChapter {
  id: string
  study_space_id: string
  learning_route_id: string
  order_index: number
  title: string
  goal: string
  summary: string
  estimated_days: number
  status: string
  source_chunk_refs: Array<Record<string, unknown>>
}

interface ChapterStudyRoute {
  id: string
  study_space_id: string
  version: number
  status: string
  title: string
}

interface ChapterStudySpace {
  id: string
  name: string
}

interface ChapterEvidence {
  source_id: string
  chunk_id: string
  chunk_index: number
  source_filename: string
  text: string
  citation: Record<string, unknown>
}

interface ChapterStudyDetail {
  chapter: ChapterStudyChapter
  route: ChapterStudyRoute
  study_space: ChapterStudySpace
  evidence: ChapterEvidence[]
  next_chapter_id: string | null
}

const DEV_AUTH_HEADERS = {
  'X-User-Id': '00000000-0000-0000-0000-000000000002',
  'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
}

const route = useRoute()
const config = useRuntimeConfig()
const chapterId = computed(() => String(route.params.id))

const detail = ref<ChapterStudyDetail | null>(null)
const loading = ref(false)
const completing = ref(false)
const errorMessage = ref('')

const chapter = computed(() => detail.value?.chapter ?? null)
const evidence = computed(() => detail.value?.evidence ?? [])
const isCompleted = computed(() => chapter.value?.status === 'completed')

function protectedHeaders() {
  return DEV_AUTH_HEADERS
}

function appendBackendMessage(base: string, error: unknown) {
  if (error instanceof Error && error.message) return `${base} ${error.message}`
  return base
}

function citationSummary(citation: Record<string, unknown>) {
  const page = citation.page_number ?? citation.page
  if (page) return `Page ${page}`
  return Object.keys(citation).length ? JSON.stringify(citation) : 'No citation metadata'
}

async function loadChapter() {
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await $fetch<ChapterStudyDetail>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}`,
      { headers: protectedHeaders() }
    )
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to load chapter.', error)
  } finally {
    loading.value = false
  }
}

async function completeCurrentChapter() {
  if (!chapter.value || isCompleted.value) return
  completing.value = true
  errorMessage.value = ''
  try {
    detail.value = await $fetch<ChapterStudyDetail>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/complete`,
      {
        method: 'POST',
        headers: protectedHeaders()
      }
    )
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to complete chapter.', error)
  } finally {
    completing.value = false
  }
}

onMounted(() => {
  loadChapter()
})
</script>

<template>
  <section class="chapter-study page-enter">
    <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>
    <p v-if="loading" class="muted">Loading chapter...</p>

    <template v-if="detail && chapter">
      <div class="topbar chapter-heading">
        <div>
          <p class="eyebrow">Chapter {{ chapter.order_index }} · {{ detail.study_space.name }}</p>
          <h1>{{ chapter.title }}</h1>
          <p>{{ detail.route.title }}</p>
        </div>
        <NuxtLink class="secondary-button back-link" :to="`/spaces/${chapter.study_space_id}`">
          Back to space
        </NuxtLink>
      </div>

      <section class="card chapter-summary">
        <div class="summary-grid">
          <div>
            <p class="eyebrow">Goal</p>
            <h2>{{ chapter.goal }}</h2>
            <p>{{ chapter.summary }}</p>
          </div>
          <dl class="chapter-meta">
            <div>
              <dt>Status</dt>
              <dd><span class="status-badge">{{ chapter.status }}</span></dd>
            </div>
            <div>
              <dt>Estimated</dt>
              <dd>{{ chapter.estimated_days }} days</dd>
            </div>
          </dl>
        </div>
      </section>

      <div class="study-grid">
        <section class="card evidence-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Source evidence</p>
              <h2>Grounding material</h2>
            </div>
            <span v-if="evidence.length" class="chunk-count">{{ evidence.length }} excerpts</span>
          </div>

          <div v-if="evidence.length" class="evidence-list">
            <article v-for="item in evidence" :key="item.chunk_id" class="evidence-card">
              <div class="evidence-header">
                <h3>{{ item.source_filename }}</h3>
                <span>Chunk #{{ item.chunk_index }}</span>
              </div>
              <p>{{ item.text }}</p>
              <small>{{ citationSummary(item.citation) }}</small>
            </article>
          </div>
          <p v-else class="empty-state">No source evidence is linked to this chapter yet.</p>
        </section>

        <aside class="card mentor-reserved">
          <p class="eyebrow">AI Mentor</p>
          <h2>Reserved for tutor chat</h2>
          <p class="muted">
            Later, this panel will answer questions using the current chapter and source evidence.
          </p>
          <textarea disabled placeholder="Ask about this chapter"></textarea>
          <button class="secondary-button" type="button" disabled>Ask mentor</button>
        </aside>
      </div>

      <section class="card chapter-actions">
        <button
          data-testid="complete-chapter"
          class="primary-button"
          type="button"
          :disabled="isCompleted || completing"
          @click="completeCurrentChapter"
        >
          {{ isCompleted ? 'Completed' : completing ? 'Completing...' : 'Mark complete' }}
        </button>
        <NuxtLink
          v-if="detail.next_chapter_id"
          class="secondary-button next-link"
          :to="`/chapters/${detail.next_chapter_id}`"
        >
          Next chapter
        </NuxtLink>
      </section>
    </template>
  </section>
</template>

<style scoped>
.chapter-study {
  display: grid;
  gap: 18px;
}

.chapter-heading,
.summary-grid,
.study-grid,
.chapter-actions,
.section-heading,
.evidence-header {
  display: flex;
  gap: 14px;
}

.chapter-heading,
.section-heading,
.evidence-header {
  align-items: center;
  justify-content: space-between;
}

.summary-grid {
  align-items: start;
  justify-content: space-between;
}

.study-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
  align-items: start;
}

.chapter-summary,
.evidence-panel,
.mentor-reserved {
  display: grid;
  gap: 16px;
}

.chapter-meta {
  display: grid;
  gap: 12px;
  min-width: 160px;
}

.chapter-meta dt {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.chapter-meta dd {
  margin: 4px 0 0;
}

.evidence-list {
  display: grid;
  gap: 12px;
}

.evidence-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  padding: 14px;
}

.evidence-card p {
  color: var(--color-text);
  white-space: pre-wrap;
}

.evidence-card small,
.muted,
.chapter-heading p {
  color: var(--color-muted);
}

.chunk-count {
  border-radius: 999px;
  padding: 5px 8px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
}

.mentor-reserved textarea {
  min-height: 120px;
  resize: vertical;
}

.back-link,
.next-link {
  text-decoration: none;
}

@media (max-width: 960px) {
  .study-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .chapter-heading,
  .chapter-actions,
  .section-heading,
  .evidence-header {
    align-items: stretch;
    flex-direction: column;
  }
}
```

- [ ] **Step 4: Run chapter page tests**

Run:

```powershell
npm run test -- tests/chapter-study.spec.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/pages/chapters/[id]/index.vue apps/web/tests/chapter-study.spec.ts
git commit -m "feat: add chapter study page"
```

---

### Task 6: Final Verification

**Files:**
- Read all changed files before finalizing.

- [ ] **Step 1: Run backend tests**

Run from `apps/api`:

```powershell
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

- [ ] **Step 3: Run frontend tests**

Run from `apps/web`:

```powershell
npm run test
```

Expected: all Vitest tests pass, including `chapter-study.spec.ts` and existing source-library tests.

- [ ] **Step 4: Run frontend typecheck and build**

Run:

```powershell
npm run typecheck
npm run build
```

Expected:

- Typecheck exits 0. Existing Vue language plugin warning is acceptable if there are no type errors.
- Build exits 0. Existing Nuxt sourcemap/deprecation warnings are acceptable.

- [ ] **Step 5: Validate Docker Compose**

Run from repo root:

```powershell
docker compose -f infra/docker-compose.yml config
```

Expected: exit code 0. Docker config access warnings can be recorded as environment-only if config prints successfully.

- [ ] **Step 6: Review diff for accidental files**

Run:

```powershell
git status --short
git diff --stat
```

Expected:

- No unrelated files staged.
- Do not stage `apps/web/package-lock.json` if it only has line-ending noise.
- Do not stage unrelated untracked Chinese docs unless the user explicitly asks.

## Final Verification Commands

Before PR or merge, record:

```powershell
cd apps\api
$env:PYTHONPATH = "$PWD"
python -m pytest -q
python -m ruff check .
cd ..\web
npm run test
npm run typecheck
npm run build
cd ..\..
docker compose -f infra/docker-compose.yml config
```

## Execution Order

1. Merge PR #5 `Add route generation foundation` into `main`.
2. Create a feature worktree such as `codex/chapter-study-page`.
3. Execute Tasks 1-6 in order.
4. Keep commits small and reviewable.
5. Preserve existing untracked Chinese docs and package-lock line-ending noise unless explicitly asked.
6. Push branch and create PR after verification.

## Self-Review

- Spec coverage: Plan covers chapter detail API, completion API, source evidence, study page, study-space entry point, reserved mentor panel, auth boundaries, and tests.
- Scope control: No real AI, no RAG answer generation, no new persistence tables, and no background workers are included.
- Type consistency: API response names and frontend TypeScript interfaces match the design spec.
- Risk control: Backend domain is separated into `chapter_study`, and frontend changes are limited to the existing study-space page plus a new chapter page.
