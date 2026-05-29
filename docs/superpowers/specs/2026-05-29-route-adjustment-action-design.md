# Route Adjustment Action Design

## Problem

Planner Actions now start focused review sessions for `review_chapter`, but `route_adjustment` actions are still passive queue items. This blocks the L1 planner from producing user-confirmed route changes.

## Decision

Add a user-confirmed execution endpoint:

- `POST /api/v1/planner-actions/{action_id}/route-draft`

The endpoint only handles `route_adjustment` actions. It creates a new draft learning route from the current active route and stores the generated draft route ID in the action payload. It marks the action `accepted`.

No active route is replaced. The existing `POST /api/v1/routes/{route_id}/activate` endpoint remains the explicit activation step.

## Initial Adjustment Support

Support the existing planner proposal kinds:

- `insert_review`: clone the active route and insert a focused review chapter after the referenced chapter.
- `extend_route`: clone the active route and append one advanced follow-up chapter.

The endpoint is idempotent. Repeated clicks reuse the already generated draft route.

## Non-goals

- No automatic activation.
- No route deletion.
- No migration.
- No LLM route rewriting in this phase.
