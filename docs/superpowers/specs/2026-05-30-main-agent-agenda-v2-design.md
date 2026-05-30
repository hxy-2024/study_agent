# Main Agent Agenda v2 Design

**Goal:** Make the dashboard recommendation behave like a Layer 1 Main Agent agenda decision, while keeping deterministic fallback available for local personal use.

**Scope:** This slice records Main Agent recommendation runs, gathers richer dashboard signals, and lets the user adjust the recommendation by available time and study intent. It does not add a full LangGraph Main Agent yet.

---

## Product Principle

This product is an AI-first learning system: the user should feel they are collaborating with an autonomous learning agent, not operating a form-heavy dashboard. Frontend controls should serve the AI interaction model. When a decision belongs to the Main Agent, the UI should expose a conversational agent entry point and show the result on the dashboard.

The Main Agent can:

- talk with the user about study intent, available time, energy, and constraints
- read authorized learning state across local study spaces
- generate and refresh dashboard recommendations
- open approved study actions such as chapters, quizzes, or study spaces
- persist recommendation runs for traceability

The Main Agent must not:

- bypass tenant/user boundaries
- mutate uploaded source material directly
- run ingestion, deletion, restore, or export without an explicit user action
- hide whether a recommendation is deterministic fallback or provider-backed

---

## Product Behavior

The dashboard "Today" card remains the primary entry point. It should answer:

- what to do first
- why this is the best next action
- how long it should take
- what else is queued
- whether the recommendation used fallback logic

The user adjusts the recommendation through a Main Agent conversation entry point, not static controls on the dashboard card. The dashboard card stays focused on the current decision. A floating Main Agent entry opens an independent conversation window where the user can say things like "I only have 15 minutes" or "I want to review weak points". The response updates the card without mutating low-level learning artifacts.

---

## Agent Boundary

Layer 1 `main_agent` owns the final recommendation and records a run.

Layer 2 signals are read-only inputs in this slice:

- unfinished chapters
- planner actions
- chapter mentor states
- mastery records
- quizzes
- recent sessions and agent runs

Layer 3 tools are not directly invoked by the dashboard. Retrieval, quiz scoring, and LLM provider calls remain behind their existing domain services.

---

## Backend Contract

Add a recommendation request shape:

```json
{
  "available_minutes": 30,
  "intent": "balanced"
}
```

`GET /api/v1/dashboard` keeps returning a default recommendation.

Add `POST /api/v1/dashboard/recommendation` to regenerate the recommendation with user preferences. Both endpoints return the same `DashboardRecommendation` schema.

The recommendation includes:

- `agent_type: "main_agent"`
- `freshness: "deterministic_fallback"`
- `strategy_version`
- `source_signals`
- `agent_run_id` when the run is persisted

---

## Recommendation Strategy

The first implementation remains deterministic but uses a richer input contract:

1. If intent is `review`, prefer stale/low mastery chapters.
2. If intent is `quiz`, prefer chapters with submitted or available quiz state.
3. If intent is `new_material`, prefer the next unfinished chapter.
4. If intent is `balanced`, prefer urgent review, then unfinished chapter, then planner action.
5. Fit estimated time to the requested available time where possible.
6. If no active learning state exists, recommend creating a study space.

This strategy is versioned as `main_agent_agenda_v2`.

---

## Persistence

Each generated recommendation writes an `agent_runs` row:

- `agent_type`: `main_agent`
- `status`: `completed`
- `summary`: primary recommendation title
- `input_payload`: user preference and signal counts
- `output_payload`: recommendation object
- `model`: `deterministic`
- `metadata`: strategy version and freshness

If persistence fails, the endpoint should still return a deterministic recommendation and omit `agent_run_id`.

---

## Frontend

The dashboard Today card adds compact controls:

- segmented time control: 15 / 30 / 60
- segmented intent control: Balanced / New / Review / Quiz
- refresh action

The controls call `POST /dashboard/recommendation` and replace the displayed recommendation. Loading and error states stay local to the card.

---

## Testing

Backend tests cover:

- `main_agent` is a valid agent type.
- default dashboard recommendation records a Main Agent run.
- review intent prefers low/stale mastery.
- new-material intent prefers unfinished chapters.
- POST recommendation honors available minutes and intent.

Frontend tests cover:

- dashboard renders Main Agent controls.
- changing intent calls the recommendation endpoint.
- refreshed recommendation replaces the card.
- refresh failure shows a readable inline error.
