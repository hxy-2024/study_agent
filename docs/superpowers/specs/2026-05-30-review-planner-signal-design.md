# Review Planner Signal Design

**Goal:** Add a real Layer 2 `review_planner` signal so the Main Agent can choose between continuing new material, reviewing weak/stale chapters, and taking quizzes.

**Scope:** This slice adds deterministic spaced-review candidates and feeds them into Main Agent recommendations. It does not add a full calendar scheduler, durable LangGraph workflow, or large frontend redesign.

---

## Product Behavior

The dashboard Main Agent recommendation should prefer review when a chapter is weak or stale. The user should see a reason that explains why review is useful now.

Examples:

- low mastery: "Review weak point: source grounding."
- stale completed chapter: "This chapter has not been reviewed recently."
- quiz weakness: "Recent quiz weak point needs review."

The recommendation remains actionable through existing chapter links.

---

## Agent Boundary

Layer 1 `main_agent` still owns the final recommendation.

Layer 2 `review_planner` produces structured candidates:

- chapter id
- study space id
- reason
- score
- due status
- weak points
- source signal

Layer 3 remains unchanged. No retrieval or LLM provider calls are needed in this slice.

---

## Deterministic Review Rules

A chapter is a review candidate when:

1. mastery score is below 70
2. mastery level is `new` or `developing`
3. mastery was updated at least 7 days ago
4. chapter is completed and has no mastery record

Candidate priority:

1. low mastery score
2. explicit weak points
3. stale update age
4. completed chapter without mastery

The first version computes candidates on read instead of persisting a schedule table. A persistent `review_schedules` table can be added later when the app needs snooze, completion, interval tuning, and review history.

---

## Backend Contract

Add an internal schema:

```json
{
  "chapter_id": "...",
  "study_space_id": "...",
  "title": "Review Retrieval",
  "reason": "Review weak point: source grounding.",
  "score": 95,
  "weak_points": ["source grounding"],
  "source": "mastery"
}
```

Expose candidate counts through `DashboardRecommendation.source_signals.review_candidates`.

The dashboard recommendation strategy accepts `review_candidates` and uses them before raw mastery records.

---

## Testing

Backend tests cover:

- low mastery creates a review candidate
- stale mastery creates a review candidate
- completed chapter without mastery creates a lower-priority candidate
- review intent uses `review_planner` candidates first
- balanced intent prefers due review over new material
- source signal metadata includes review candidate count

Frontend tests only need to confirm source metadata does not break rendering. No visual redesign is included.

