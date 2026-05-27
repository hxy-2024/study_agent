# Chapter Study Page Design Spec

Date: 2026-05-27

## Decision Summary

Build the first chapter-level study execution experience. A user can open an active route chapter, read its goal and summary, inspect source evidence from RAG chunks, mark the chapter complete, and move to the next chapter.

This phase does not connect a real AI tutor. It reserves an AI mentor panel and backend boundary so a later RAG + LLM chat workflow can attach without changing the chapter study page layout or core chapter state machine.

## Product Goal

Complete the next MVP learning loop:

```text
Import materials -> ingest chunks -> generate route -> activate route -> study chapter -> complete chapter
```

The user should feel that generated routes are actionable. After activating a route, each chapter becomes a concrete study surface with source evidence and clear progress actions.

## Scope

In scope:

- Chapter study page at `/chapters/{chapter_id}`.
- Link from study-space route chapter rows to the study page.
- Tenant-safe chapter detail API.
- Tenant-safe chapter completion API.
- Source chunk excerpts for the chapter's `source_chunk_refs`.
- Chapter state transition:
  - Completing the current chapter sets it to `completed`.
  - The next incomplete chapter in the same route becomes `active`.
  - If no next chapter exists, all chapters remain completed or not started as stored.
- Reserved AI mentor panel with disabled input and clear "coming later" state.
- Tests for service behavior, API auth boundaries, frontend rendering, and completion action.

Out of scope:

- Real LLM calls.
- RAG answer generation.
- Streaming chat.
- Persisted tutor messages.
- Quiz generation.
- Spaced repetition cards.
- Rich chapter editing.
- Route reordering.
- Background jobs.

## User Experience

### Entry Point

On the study space detail page, active or draft route chapter rows show a `Study` action. The action navigates to:

```text
/chapters/{chapter_id}
```

For this phase, chapter rows can remain visually quiet and utilitarian. The `Study` action should be a text button or icon+text button aligned with the existing Fresh Teal workspace style.

### Chapter Study Layout

The page uses a two-column desktop layout and a single-column mobile layout:

```text
+----------------------------------------------+
| Top bar: Back to space / route status         |
+----------------------------------------------+
| Chapter title                                 |
| Goal, summary, status badge, estimated days   |
+--------------------------+-------------------+
| Source Evidence          | AI Mentor Reserved |
| - chunk excerpt cards    | - disabled input   |
| - source/chunk metadata  | - future state     |
| - empty state fallback   |                   |
+--------------------------+-------------------+
| Mark complete / Next chapter                  |
+----------------------------------------------+
```

### Required States

- Loading: show page skeleton or muted loading text.
- Loaded with evidence: show ordered source excerpt cards.
- Loaded without evidence: show an empty evidence state explaining that this chapter was generated without source references.
- Completed chapter: show completed status and keep the completion button disabled.
- Completion in progress: disable actions and show active button text.
- Completion error: show an error alert.
- Missing or unauthorized chapter: backend returns 404; frontend shows a concise error state.

## Backend API

Add authenticated APIs under `/api/v1`.

```text
GET  /chapters/{chapter_id}
POST /chapters/{chapter_id}/complete
```

### GET `/chapters/{chapter_id}`

Returns chapter detail for the authorized tenant.

Response:

```json
{
  "chapter": {
    "id": "uuid",
    "study_space_id": "uuid",
    "learning_route_id": "uuid",
    "order_index": 1,
    "title": "Chapter title",
    "goal": "Chapter goal",
    "summary": "Chapter summary",
    "estimated_days": 3,
    "status": "active",
    "source_chunk_refs": []
  },
  "route": {
    "id": "uuid",
    "study_space_id": "uuid",
    "version": 1,
    "status": "active",
    "title": "Route title"
  },
  "study_space": {
    "id": "uuid",
    "name": "Study space name"
  },
  "evidence": [
    {
      "source_id": "uuid",
      "chunk_id": "uuid",
      "chunk_index": 0,
      "source_filename": "notes.md",
      "text": "Chunk excerpt...",
      "citation": {
        "page_number": 1
      }
    }
  ],
  "next_chapter_id": "uuid-or-null"
}
```

Rules:

- Tenant id comes only from `CurrentUserContext`.
- Clients never send tenant scope.
- Chapter lookup filters by `Chapter.tenant_id == context.tenant_id`.
- Evidence lookup filters chunks by tenant id, chapter study space id, referenced chunk ids, and `is_active = true`.
- Evidence text is bounded to a small excerpt, initially 700 characters.
- Missing chapter returns 404.

### POST `/chapters/{chapter_id}/complete`

Marks a chapter complete and activates the next incomplete chapter in the same learning route.

Response shape matches `GET /chapters/{chapter_id}` for the completed chapter, with updated status and next chapter id.

Rules:

- Completing an already completed chapter is idempotent and returns the current detail.
- Completion only affects chapters in the same tenant and learning route.
- The next chapter is the lowest `order_index` chapter after the completed chapter whose status is not `completed`.
- The next chapter status becomes `active`.
- Other not-started chapters remain `not_started`.
- If the route has no remaining incomplete chapter, no next chapter is activated.

## Backend Domain Design

Create a focused `chapter_study` domain:

```text
apps/api/app/domain/chapter_study/
  __init__.py
  schemas.py
  service.py
```

Responsibilities:

- `schemas.py`: request/response DTOs for chapter study APIs.
- `service.py`: tenant-safe chapter lookup, evidence loading, next chapter calculation, completion transition.

Add API routes:

```text
apps/api/app/api/routes_chapter_study.py
```

Register the route module in:

```text
apps/api/app/api/router.py
```

No new database table is required in this phase. Existing `chapters`, `learning_routes`, `study_spaces`, `sources`, and `source_chunks` contain enough state for the first execution page.

## Frontend Design

Modify:

```text
apps/web/pages/spaces/[id]/index.vue
```

Add:

```text
apps/web/pages/chapters/[id]/index.vue
```

Chapter page behavior:

- Fetch `GET /api/v1/chapters/{chapter_id}` on mount.
- Render title, goal, summary, status, estimated days, study space name, and route title.
- Render source evidence cards.
- Render reserved AI mentor panel:
  - heading: `AI Mentor`
  - disabled textarea/input
  - disabled ask button
  - short state text that tutor chat will use this chapter and evidence later
- `Mark complete` calls `POST /api/v1/chapters/{chapter_id}/complete`.
- If response includes `next_chapter_id`, show `Next chapter` action linking to that chapter.
- Keep the visual style aligned with the Fresh Teal app shell: teal accents, restrained cards, dense operational layout, no marketing hero.

## Security and Tenant Rules

- Both endpoints require `get_authorized_user_context`.
- Client-supplied tenant ids are not accepted.
- Chapter, route, source, and chunk reads are scoped to the authorized tenant.
- Cross-tenant chapter ids return 404, not 403, to avoid resource existence leakage.
- Future AI tutor endpoints must keep provider keys server-side only.

## Testing Strategy

Backend tests:

- Chapter detail returns authorized chapter data.
- Chapter detail rejects missing or outside-tenant chapters as 404.
- Evidence loading only returns active chunks in the same tenant/study space and referenced chunk ids.
- Completion marks current chapter completed.
- Completion activates the next incomplete chapter.
- Completion is idempotent for already completed chapters.
- API tests verify tenant id is derived from auth context, not request payload.

Frontend tests:

- Study space route panel renders `Study` action for chapter rows.
- Chapter page renders title, goal, summary, evidence, and reserved AI mentor panel.
- Empty evidence state renders when no evidence exists.
- Clicking `Mark complete` calls the completion API.
- Completion response updates status and renders `Next chapter` when available.

## Acceptance Criteria

- A user can navigate from a route chapter row to a chapter study page.
- The chapter page shows the chapter's study goal, summary, status, estimated days, and source evidence.
- A chapter can be marked complete through an authenticated API.
- Completing a chapter activates the next incomplete chapter in the same route.
- The implementation is tenant-safe and does not accept client tenant scope.
- The AI mentor panel is visibly reserved but does not call LLM or RAG answer generation.
- Existing route generation, source library, and app shell tests continue passing.

## Future Extension

The reserved AI mentor panel will later connect to:

```text
POST /api/v1/chapters/{chapter_id}/mentor-sessions
POST /api/v1/mentor-sessions/{session_id}/messages
```

Those future endpoints can use the same chapter detail and evidence contract from this phase as their grounding context.
