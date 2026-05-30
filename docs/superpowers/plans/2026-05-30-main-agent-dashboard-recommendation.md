# Main Agent Dashboard Recommendation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Layer 1 Main Agent recommendation to the dashboard so the homepage clearly answers what to study first today.

**Architecture:** Add a focused dashboard recommendation module that builds a deterministic Main Agent fallback recommendation from existing study state. Extend the dashboard API schema and service to include `today_recommendation`, then update the Nuxt dashboard page to render that recommendation as the primary Today card. This keeps the contract stable for later LangGraph/LLM orchestration.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, pytest, Nuxt/Vue, Vitest.

---

## File Structure

- Create `apps/api/app/domain/dashboard/recommendations.py`
  - Pure recommendation builders and response mapping.
- Modify `apps/api/app/domain/dashboard/schemas.py`
  - Add `DashboardRecommendation` and `DashboardRecommendationAction`.
- Modify `apps/api/app/domain/dashboard/service.py`
  - Query minimal chapter/mastery/quiz data and attach `today_recommendation`.
- Modify `apps/api/tests/test_dashboard_service.py`
  - Add service tests for primary recommendation and empty-state recommendation.
- Modify `apps/web/pages/index.vue`
  - Render Main Agent Today card from `dashboard.today_recommendation`.
- Modify `apps/web/tests/dashboard.spec.ts`
  - Add UI tests for Main Agent card and secondary queue.

---

### Task 1: Backend Recommendation Schema and Pure Builder

**Files:**
- Create: `apps/api/app/domain/dashboard/recommendations.py`
- Modify: `apps/api/app/domain/dashboard/schemas.py`
- Test: `apps/api/tests/test_dashboard_recommendations.py`

- [ ] **Step 1: Write the failing recommendation builder tests**

Create `apps/api/tests/test_dashboard_recommendations.py`:

```python
import uuid
from types import SimpleNamespace

from app.domain.dashboard.recommendations import build_main_agent_recommendation


def test_main_agent_recommends_active_chapter_first() -> None:
    space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    recommendation = build_main_agent_recommendation(
        spaces=[
            SimpleNamespace(id=space_id, name="RAG Basics", status="active", target_days=14),
        ],
        chapters=[
            SimpleNamespace(
                id=chapter_id,
                study_space_id=space_id,
                title="Retrieval",
                status="active",
                order_index=1,
            )
        ],
        planner_actions=[],
        mastery_records=[],
    )

    assert recommendation is not None
    assert recommendation.agent_type == "main_agent"
    assert recommendation.recommendation_type == "continue_chapter"
    assert recommendation.title == "Continue Retrieval"
    assert recommendation.action_url == f"/chapters/{chapter_id}"
    assert recommendation.study_space_id == space_id
    assert recommendation.chapter_id == chapter_id
    assert recommendation.freshness == "deterministic_fallback"


def test_main_agent_recommends_create_space_when_no_space_exists() -> None:
    recommendation = build_main_agent_recommendation(
        spaces=[],
        chapters=[],
        planner_actions=[],
        mastery_records=[],
    )

    assert recommendation is not None
    assert recommendation.recommendation_type == "create_space"
    assert recommendation.action_url == "/spaces/new"
    assert recommendation.action_label == "Create space"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd apps/api
$env:PYTHONPATH = "$PWD"
F:\AIproject\study_agent\apps\api\.venv\Scripts\python.exe -m pytest tests/test_dashboard_recommendations.py -q
```

Expected: fail because `app.domain.dashboard.recommendations` does not exist.

- [ ] **Step 3: Add schema models**

In `apps/api/app/domain/dashboard/schemas.py`, add:

```python
class DashboardRecommendationAction(BaseModel):
    title: str
    action_label: str
    action_url: str
    recommendation_type: str
    reason: str | None = None
    estimated_minutes: int | None = None
    study_space_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None


class DashboardRecommendation(DashboardRecommendationAction):
    agent_type: str = "main_agent"
    freshness: str = "deterministic_fallback"
    secondary_actions: list[DashboardRecommendationAction] = Field(default_factory=list)
```

Update `DashboardResponse`:

```python
today_recommendation: DashboardRecommendation | None = None
```

- [ ] **Step 4: Add pure builder**

Create `apps/api/app/domain/dashboard/recommendations.py`:

```python
from typing import Any

from app.db.models import ChapterStatus, PlannerActionStatus
from app.domain.dashboard.schemas import DashboardRecommendation, DashboardRecommendationAction


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _space_name(spaces: list[Any], study_space_id) -> str:
    for space in spaces:
        if space.id == study_space_id:
            return getattr(space, "name", "this space")
    return "this space"


def _chapter_action(chapter: Any, spaces: list[Any], reason: str) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=f"Continue {chapter.title}",
        action_label="Study now",
        action_url=f"/chapters/{chapter.id}",
        recommendation_type="continue_chapter",
        reason=reason,
        estimated_minutes=25,
        study_space_id=chapter.study_space_id,
        chapter_id=chapter.id,
    )


def _planner_action(action: Any) -> DashboardRecommendationAction:
    return DashboardRecommendationAction(
        title=action.title,
        action_label="Review action",
        action_url=f"/chapters/{action.chapter_id}" if action.chapter_id else "/",
        recommendation_type="planner_action",
        reason="Your planner has an open recommendation.",
        estimated_minutes=15,
        study_space_id=action.study_space_id,
        chapter_id=action.chapter_id,
    )


def build_main_agent_recommendation(
    *,
    spaces: list[Any],
    chapters: list[Any],
    planner_actions: list[Any],
    mastery_records: list[Any],
) -> DashboardRecommendation | None:
    candidates: list[DashboardRecommendationAction] = []

    active_or_next = sorted(
        [
            chapter
            for chapter in chapters
            if _enum_value(getattr(chapter, "status", "")) != ChapterStatus.completed.value
        ],
        key=lambda chapter: (str(chapter.study_space_id), chapter.order_index, str(chapter.id)),
    )
    for chapter in active_or_next:
        reason = f"{_space_name(spaces, chapter.study_space_id)} has an unfinished chapter ready."
        candidates.append(_chapter_action(chapter, spaces, reason))

    open_actions = [
        action
        for action in planner_actions
        if _enum_value(getattr(action, "status", "")) in {PlannerActionStatus.proposed.value, PlannerActionStatus.accepted.value}
    ]
    candidates.extend(_planner_action(action) for action in open_actions)

    if not candidates:
        return DashboardRecommendation(
            title="Create your first study space",
            action_label="Create space",
            action_url="/spaces/new",
            recommendation_type="create_space",
            reason="No active learning space exists yet.",
            estimated_minutes=10,
        )

    primary = candidates[0]
    return DashboardRecommendation(
        **primary.model_dump(),
        secondary_actions=candidates[1:4],
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```powershell
cd apps/api
$env:PYTHONPATH = "$PWD"
F:\AIproject\study_agent\apps\api\.venv\Scripts\python.exe -m pytest tests/test_dashboard_recommendations.py -q
```

Expected: 2 passed.

---

### Task 2: Dashboard Service Integration

**Files:**
- Modify: `apps/api/app/domain/dashboard/service.py`
- Test: `apps/api/tests/test_dashboard_service.py`

- [ ] **Step 1: Add failing service assertion**

In `apps/api/tests/test_dashboard_service.py`, extend the fake session to return chapters on a fifth query, or add a new focused test:

```python
async def test_dashboard_summary_includes_main_agent_recommendation() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    class FakeScalars:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class FakeSession:
        def __init__(self):
            self.calls = 0

        async def scalars(self, _statement):
            self.calls += 1
            if self.calls == 1:
                return FakeScalars([
                    StudySpace(id=study_space_id, tenant_id=tenant_id, owner_user_id=user_id, name="RAG Basics", goal="Learn retrieval", target_days=14)
                ])
            if self.calls == 5:
                return FakeScalars([
                    Chapter(id=chapter_id, tenant_id=tenant_id, study_space_id=study_space_id, title="Retrieval", status=ChapterStatus.active, order_index=1)
                ])
            return FakeScalars([])

    response = await get_dashboard_summary(session=FakeSession(), tenant_id=tenant_id, user_id=user_id)

    assert response.today_recommendation is not None
    assert response.today_recommendation.agent_type == "main_agent"
    assert response.today_recommendation.action_url == f"/chapters/{chapter_id}"
```

- [ ] **Step 2: Run service tests to verify failure**

Run:

```powershell
cd apps/api
$env:PYTHONPATH = "$PWD"
F:\AIproject\study_agent\apps\api\.venv\Scripts\python.exe -m pytest tests/test_dashboard_service.py -q
```

Expected: fail because `today_recommendation` is not populated.

- [ ] **Step 3: Query chapters and call builder**

In `apps/api/app/domain/dashboard/service.py`:

- import `Chapter`
- import `build_main_agent_recommendation`
- add a `chapter_rows` query scoped to active space ids:

```python
chapter_rows = await session.scalars(
    select(Chapter)
    .where(
        Chapter.tenant_id == tenant_id,
        Chapter.study_space_id.in_(active_space_ids),
    )
    .order_by(Chapter.study_space_id, Chapter.order_index, Chapter.id)
)
chapters = list(chapter_rows)
```

Pass `today_recommendation=build_main_agent_recommendation(...)` into `DashboardResponse`.

- [ ] **Step 4: Run service tests**

Run:

```powershell
cd apps/api
$env:PYTHONPATH = "$PWD"
F:\AIproject\study_agent\apps\api\.venv\Scripts\python.exe -m pytest tests/test_dashboard_service.py tests/test_dashboard_recommendations.py -q
```

Expected: all pass.

---

### Task 3: Dashboard UI

**Files:**
- Modify: `apps/web/pages/index.vue`
- Test: `apps/web/tests/dashboard.spec.ts`

- [ ] **Step 1: Add failing dashboard UI test**

In `apps/web/tests/dashboard.spec.ts`, add:

```ts
it('renders the main agent today recommendation as the primary action', async () => {
  fetchMock.mockResolvedValue({
    spaces: [
      {
        id: 'space-1',
        name: 'RAG Basics',
        goal: 'Learn retrieval',
        status: 'active',
        target_days: 14
      }
    ],
    pending_actions: [],
    supervision_refresh_count: 0,
    recent_agent_runs: [],
    today_recommendation: {
      agent_type: 'main_agent',
      title: 'Continue Retrieval',
      action_label: 'Study now',
      action_url: '/chapters/chapter-1',
      recommendation_type: 'continue_chapter',
      reason: 'RAG Basics has an unfinished chapter ready.',
      estimated_minutes: 25,
      study_space_id: 'space-1',
      chapter_id: 'chapter-1',
      freshness: 'deterministic_fallback',
      secondary_actions: [
        {
          title: 'Review citations',
          action_label: 'Review',
          action_url: '/chapters/chapter-2',
          recommendation_type: 'review_chapter'
        }
      ]
    }
  })

  const wrapper = mountPage()
  await flushPromises()

  expect(wrapper.text()).toContain('Main Agent')
  expect(wrapper.text()).toContain('Continue Retrieval')
  expect(wrapper.text()).toContain('RAG Basics has an unfinished chapter ready.')
  expect(wrapper.find('a[href="/chapters/chapter-1"]').text()).toContain('Study now')
  expect(wrapper.text()).toContain('Review citations')
})
```

- [ ] **Step 2: Run UI test to verify failure**

Run:

```powershell
cd apps/web
npm run test -- dashboard.spec.ts
```

Expected: fail because the Main Agent recommendation is not rendered.

- [ ] **Step 3: Add UI types and computed fallback**

In `apps/web/pages/index.vue`, add `DashboardRecommendationAction` and `DashboardRecommendation` interfaces, extend `DashboardSummary`, and add:

```ts
const todayRecommendation = computed(() => dashboard.value?.today_recommendation ?? null)
const todayActionHref = computed(() => todayRecommendation.value?.action_url ?? continueHref.value)
const todayActionLabel = computed(() => todayRecommendation.value?.action_label ?? continueLabel.value)
```

- [ ] **Step 4: Replace primary continue card content**

Update the main card to show:

```vue
<p class="eyebrow">Main Agent</p>
<h2>{{ todayRecommendation?.title ?? currentSpace.name }}</h2>
<p>{{ todayRecommendation?.reason ?? currentSpace.goal }}</p>
<small v-if="todayRecommendation?.estimated_minutes">{{ todayRecommendation.estimated_minutes }} min suggested</small>
<NuxtLink class="primary-button" :to="todayActionHref">{{ todayActionLabel }}</NuxtLink>
```

Render secondary queue if `todayRecommendation.secondary_actions.length`.

- [ ] **Step 5: Run UI tests**

Run:

```powershell
cd apps/web
npm run test -- dashboard.spec.ts
```

Expected: dashboard tests pass.

---

### Task 4: Verification

**Files:**
- No code files unless failures require fixes.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
cd apps/api
$env:PYTHONPATH = "$PWD"
F:\AIproject\study_agent\apps\api\.venv\Scripts\python.exe -m pytest tests/test_dashboard_recommendations.py tests/test_dashboard_service.py tests/test_dashboard_routes.py -q
```

Expected: pass.

- [ ] **Step 2: Run frontend focused tests**

Run:

```powershell
cd apps/web
npm run test -- dashboard.spec.ts
```

Expected: pass.

- [ ] **Step 3: Run lint and broader tests**

Run:

```powershell
cd apps/api
$env:PYTHONPATH = "$PWD"
F:\AIproject\study_agent\apps\api\.venv\Scripts\python.exe -m ruff check app tests
F:\AIproject\study_agent\apps\api\.venv\Scripts\python.exe -m pytest -q
cd ..\web
npm run test
npm run typecheck
npm run build
```

Expected: pass. The existing Vue/Volar plugin warning during typecheck is acceptable only if the command exits 0.

