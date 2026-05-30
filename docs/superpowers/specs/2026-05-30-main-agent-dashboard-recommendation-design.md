# Main Agent Dashboard Recommendation Design

**Goal:** Put a Layer 1 Main Agent recommendation on the homepage so the user can see what to study first today.

**Scope:** This first implementation creates the contract, deterministic fallback, API integration, and dashboard display. It does not add the interactive Main Agent chat yet.

---

## Product Behavior

The dashboard should show one prominent "Today" recommendation from the Main Agent:

- title
- recommendation type
- reason
- estimated minutes
- primary action URL
- source signal metadata
- 2-3 secondary actions

The recommendation should feel like a coach decision, not a static rule list. It should mention why now is the right action.

When the LLM provider is unavailable, the service uses deterministic fallback logic with the same output shape.

---

## Agent Boundary

This feature follows `docs/superpowers/specs/2026-05-30-agent-layer-model-design.md`.

- Layer 1: `main_agent` owns the final dashboard recommendation.
- Layer 2: existing planner, mentor, mastery, and session signals are inputs.
- Layer 3: retrieval, quiz, source, and provider tools remain execution utilities.

The first PR does not add a LangGraph Main Agent. It creates the stable service/API/UI contract so LangGraph can replace or wrap the deterministic generator later.

---

## Recommendation Inputs

The service reads:

- active study spaces
- chapters in active routes
- planner actions
- space planner states
- chapter mentor states
- mastery records
- quizzes
- recent agent runs

The first version uses existing tables only.

---

## Deterministic Fallback Priority

The fallback generator produces a primary action using this order:

1. Continue an active or first incomplete chapter.
2. Review a chapter with low mastery or stale mastery.
3. Complete a proposed/accepted planner action with a chapter link.
4. Prepare a route for the newest active study space.
5. Create a study space when no active space exists.

Secondary actions are the next best candidates after the primary action.

---

## API Contract

Extend `GET /api/v1/dashboard` with:

```json
{
  "today_recommendation": {
    "agent_type": "main_agent",
    "title": "Continue Retrieval Basics",
    "action_label": "Study now",
    "action_url": "/chapters/<id>",
    "recommendation_type": "continue_chapter",
    "reason": "You have an active chapter and no higher-priority review due.",
    "estimated_minutes": 25,
    "study_space_id": "<uuid>",
    "chapter_id": "<uuid>",
    "freshness": "deterministic_fallback",
    "secondary_actions": [
      {
        "title": "Review citations",
        "action_label": "Review",
        "action_url": "/chapters/<id>",
        "recommendation_type": "review_chapter"
      }
    ]
  }
}
```

The field can be `null` only if the backend cannot build even a fallback recommendation.

---

## Dashboard UI

The homepage current "Continue" card becomes the Main Agent Today card.

It should show:

- "Main Agent" eyebrow
- recommendation title
- reason
- estimated minutes
- primary CTA
- small secondary queue

Existing data safety export and archived-space panels stay below the main Today card.

---

## Testing

Backend:

- service chooses active/incomplete chapter first
- service chooses create-space when no spaces exist
- dashboard response includes `today_recommendation`
- route tests still verify authorized context

Frontend:

- dashboard renders the Main Agent Today recommendation
- primary CTA points to the backend-provided action URL
- secondary actions render when present
- fallback old behavior does not break when the field is absent

