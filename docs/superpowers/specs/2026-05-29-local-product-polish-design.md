# Local Product Polish Design

## Product Positioning

This phase targets a local personal learning product, not a multi-user SaaS. Authentication and tenant onboarding stay out of scope. The priority is reducing local friction and improving the personal study loop.

## Ordered Scope

1. Local one-command startup and health checks.
2. Personal learning dashboard / today workspace.
3. Source import improvements.
4. Chapter notes and lightweight highlights.

## Delivery Strategy

Deliver each task as an independent, testable slice. Keep APIs deterministic and local-first. Avoid background workers until local flows are stable.

## Non-goals

- No production auth.
- No multi-user billing/team features.
- No automatic route activation.
- No large UI redesign outside the touched flows.
