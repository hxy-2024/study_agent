# Planner Action Execution Design

## Problem

Planner Actions can be generated, accepted, completed, or dismissed, but they do not yet start concrete study work. This leaves the agent loop at the recommendation layer.

## Decision

Add a user-confirmed execution endpoint for `review_chapter` actions:

- `POST /api/v1/planner-actions/{action_id}/start-review`

The endpoint creates a focused mentor session for the action's chapter, marks the action `accepted`, and stores execution metadata in `PlannerAction.payload`.

The endpoint is idempotent. If the action already points to a review session, it returns that session instead of creating another one.

## UX

Planner action rows gain a `Start review` button for active `review_chapter` actions. Clicking it starts or reuses the focused session and navigates to:

```text
/chapters/{chapter_id}?session_id={session_id}
```

The chapter page prefers the query `session_id` when selecting the mentor session.

## Non-goals

- No route mutation.
- No background worker.
- No new action type.
- No migration.
