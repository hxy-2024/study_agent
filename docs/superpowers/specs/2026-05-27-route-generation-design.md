# Route Generation Foundation Design Spec

Date: 2026-05-27

## Decision Summary

Build the first production-ready learning route foundation for study_agent. The system will persist formal learning routes and chapters, generate draft routes from a study space goal and available source chunks, and let users activate a route for study.

The first implementation uses a deterministic rule-based generator. It must be isolated behind a `RouteGenerator` interface so a later LangGraph or LLM generator can replace it without changing API contracts, persistence, or frontend behavior.

## Product Goal

This phase completes the next step in the MVP learning loop:

```text
Import materials -> ingest chunks -> generate route -> study by chapter
```

The user should be able to open a study space, generate a route draft, inspect the generated chapters, and activate a route. The route quality can be simple in this phase, but the system boundaries must be production-grade.

## Scope

In scope:

- Formal persistence for learning routes and chapters.
- Deterministic route draft generation.
- Tenant-safe backend APIs for route draft creation, route listing, chapter listing, and route activation.
- Source chunk awareness when chunks exist.
- Goal-based fallback generation when no chunks exist.
- Frontend display of route/chapter state on the study space detail page.
- Tests for route generation, tenant isolation, route activation, and frontend display.

Out of scope:

- Real LLM calls.
- LangGraph workflow execution.
- Streaming generation.
- User editing of route drafts.
- Route diff and approval UI.
- Chapter study page.
- Chat sessions, quizzes, mastery, and review cards.
- Background worker queue.

## Data Model

Add two tables.

```text
learning_routes
  id
  tenant_id
  study_space_id
  version
  status
  title
  summary
  generation_strategy
  created_at
  activated_at

chapters
  id
  tenant_id
  study_space_id
  learning_route_id
  order_index
  title
  goal
  summary
  estimated_days
  status
  source_chunk_refs
  created_at
```

Route status values:

```text
draft
active
archived
```

Chapter status values:

```text
not_started
active
completed
```

Rules:

- Every route and chapter is tenant-scoped.
- A study space can have multiple routes.
- Only one route per study space should be active at a time.
- Chapters belong to exactly one route.
- `source_chunk_refs` stores a compact JSON array of chunk references used to justify chapter creation. Each item should include at least `source_id`, `chunk_id`, and `chunk_index`.
- `StudySpace.route_outline` remains as a compatibility summary for existing clients. It should be updated when a route is activated, but it is no longer the source of truth.

## Generator Boundary

Define a route generator interface in the backend domain layer.

Conceptual contract:

```python
class RouteGenerator(Protocol):
    async def generate(self, request: RouteGenerationRequest) -> RouteGenerationResult:
        ...
```

`RouteGenerationRequest` includes:

- Tenant id.
- Study space id.
- Study space name, goal, level, intensity, and target days.
- A bounded list of source chunk excerpts.

`RouteGenerationResult` includes:

- Route title.
- Route summary.
- Generation strategy.
- Ordered chapter drafts.

`ChapterDraft` includes:

- Title.
- Goal.
- Summary.
- Estimated days.
- Source chunk references.

First implementation:

```text
DeterministicRouteGenerator
```

Behavior:

- If source chunks exist, group bounded excerpts into 3-6 chapter themes.
- If no chunks exist, generate a 3-chapter route from the goal and target days.
- Divide `target_days` across chapters with a minimum of 1 day each.
- Use stable output so tests are deterministic.
- Never call external model providers.

The deterministic generator is not meant to be perfect. It exists to lock down contracts, persistence, and UI behavior before introducing model variability.

## Backend API

Add these authenticated APIs under `/api/v1`.

```text
POST /study-spaces/{study_space_id}/route-drafts
GET  /study-spaces/{study_space_id}/routes
GET  /study-spaces/{study_space_id}/chapters
POST /routes/{route_id}/activate
```

### POST `/study-spaces/{study_space_id}/route-drafts`

Creates a draft route and draft chapters.

Request body:

```json
{
  "max_chapters": 5
}
```

`max_chapters` defaults to 5 and is bounded between 3 and 8.

Response:

```json
{
  "route": {
    "id": "uuid",
    "study_space_id": "uuid",
    "version": 2,
    "status": "draft",
    "title": "Learning route",
    "summary": "Route summary",
    "generation_strategy": "deterministic",
    "created_at": "datetime",
    "activated_at": null
  },
  "chapters": [
    {
      "id": "uuid",
      "learning_route_id": "uuid",
      "order_index": 1,
      "title": "Chapter title",
      "goal": "Chapter goal",
      "summary": "Chapter summary",
      "estimated_days": 4,
      "status": "not_started",
      "source_chunk_refs": []
    }
  ]
}
```

Error behavior:

- `404` if the study space is not found in the authorized tenant.
- `400` if route generation cannot produce a valid route.

### GET `/study-spaces/{study_space_id}/routes`

Returns all routes for the study space, newest first, with their chapters.

### GET `/study-spaces/{study_space_id}/chapters`

Returns chapters for the active route. If there is no active route, returns an empty list.

This endpoint is intentionally active-route scoped because the chapter study page should use the route the user is currently studying.

### POST `/routes/{route_id}/activate`

Activates a draft route.

Rules:

- The route must belong to the authorized tenant.
- Existing active routes in the same study space become archived.
- The selected route becomes active.
- The first chapter becomes active; other incomplete chapters remain `not_started`.
- `StudySpace.route_outline` is updated from the activated chapters for compatibility.

Error behavior:

- `404` if route does not exist in tenant.
- `400` if the route is already archived or cannot be activated.

## Frontend Behavior

Update the study space detail page only.

Required states:

- No active route: show a clean empty route panel with `Generate route`.
- Draft generated: show generated chapters and an `Activate route` action.
- Active route: show route title, summary, and ordered chapters.
- Generating: disable generation button and show loading state.
- Activation failure: show an error alert.

Do not build the chapter study page in this phase. Chapter rows can be non-clickable or visually marked as future navigation.

The page should stay aligned with the Fresh Teal Learning Workspace design:

- Route panel sits above source library.
- Source library remains available below route state.
- Right rail can continue showing AI mentor/source guidance.
- Buttons, badges, empty states, and cards use the shared design system.

## Tenant and Security Rules

- Routes and chapters must derive tenant context from authenticated request context.
- Clients must not provide `tenant_id` in route generation or activation requests.
- Generation can only read source chunks from the authorized tenant and study space.
- Activation can only affect routes in the same tenant and study space.
- Later LLM integration must never expose model keys to the browser.

## Source Chunk Use

The deterministic generator should load a bounded number of active chunks for the study space.

Initial bounds:

- Maximum chunks considered: 24.
- Maximum excerpt length per chunk: 500 characters.
- Ordered by source creation and chunk index or by existing stable chunk order.

Chunk text is used only as signal for chapter titles/summaries. The implementation should store chunk references, not full duplicated chunk text, inside chapter records.

If no chunks exist, route generation still works from the study goal.

## Compatibility

The existing `create_route_outline` helper in `study_spaces.service` currently produces a simple route outline. This phase should either replace it with the deterministic generator's fallback logic or keep it as a thin compatibility wrapper over the new generator logic.

Existing study space create behavior must not break. Creating a study space may still populate `route_outline`, but formal `learning_routes` are generated through the new route draft API.

## Testing Strategy

Backend tests:

- Deterministic generator uses goal when no chunks exist.
- Deterministic generator uses chunk references when chunks exist.
- Route draft endpoint derives tenant from auth context.
- Route draft endpoint rejects study spaces outside tenant.
- Route activation archives old active route and activates selected route.
- Active chapters endpoint returns only the active route's chapters.
- `StudySpace.route_outline` updates on activation.

Frontend tests:

- Study space page renders route empty state and `Generate route`.
- Clicking `Generate route` calls route draft API and renders chapters.
- Clicking `Activate route` calls activation API and shows active chapters.
- Existing source-library upload and chunk preview tests continue passing.

Migration tests:

- Alembic history includes the route generation migration.
- Models import without relationship errors.

## Observability and Future Extension

This phase does not add full `agent_runs`, but it should keep generation metadata in `learning_routes.generation_strategy`.

Future LLM route generation can add:

- Prompt templates.
- Model provider metadata.
- Token usage.
- `agent_runs` linkage.
- Human approval diff before route activation.

## Acceptance Criteria

- A tenant-authorized user can generate a route draft for a study space.
- The draft is persisted as a `learning_routes` row with ordered `chapters`.
- A route can be activated, archiving prior active routes.
- Active chapters are retrievable through a stable API.
- The frontend study space page can generate, activate, and display routes.
- The deterministic generator is isolated behind an interface that can be replaced later.
- Existing source library upload, ingestion, retrieval preview, and study space creation behavior continue to pass tests.
