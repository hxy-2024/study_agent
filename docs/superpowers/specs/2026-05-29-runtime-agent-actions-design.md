# Runtime-driven Agent Actions Design

## Goal

Turn recent Session Tutor runtime signals into explicit review actions in the existing `planner_actions` queue.

## Product Behavior

The learner can generate actions from runtime signals in two places:

- Study Space page: creates review actions from recent tutor runs across the space.
- Chapter page: creates review actions from recent tutor runs for the current chapter.

Generated actions are not executed automatically. They enter the existing planner action queue as `proposed` review actions, where the learner can accept, complete, or dismiss them.

## Source Signals

This phase reads completed L3 `AgentRun` rows with `agent_type=session_tutor`.

Signals that produce review actions:

- `needs_review=true`: create a focused review action.
- `confusion_detected=true`: create a confusion follow-up action.
- `evidence_used=false`: create a citation-grounding action.

Other signals are preserved in action payload evidence but do not create separate actions.

## Backend Contract

Add:

- `POST /api/v1/planner-actions/from-runtime-signals`

Request:

```json
{
  "study_space_id": "00000000-0000-0000-0000-000000000101",
  "chapter_id": "00000000-0000-0000-0000-000000000601"
}
```

`chapter_id` is optional. When omitted, the endpoint scans the study space. When present, the endpoint scans only that chapter.

Response:

```json
{
  "actions": [
    {
      "id": "00000000-0000-0000-0000-000000000801",
      "study_space_id": "00000000-0000-0000-0000-000000000101",
      "chapter_id": "00000000-0000-0000-0000-000000000601",
      "action_type": "review_chapter",
      "status": "proposed",
      "title": "Review tutor confusion in Retrieval Basics",
      "rationale": "Recent tutor signals show confusion_detected and needs_review.",
      "payload": {
        "source": "runtime_signal",
        "agent_run_id": "00000000-0000-0000-0000-000000000901",
        "session_id": "00000000-0000-0000-0000-000000000701",
        "signal_types": ["confusion_detected", "needs_review"]
      }
    }
  ]
}
```

## Safety Rules

- Use `CurrentUserContext`; reject client-supplied tenant/user scope.
- Verify the study space belongs to the current user.
- If `chapter_id` is provided, verify it belongs to the study space and tenant.
- Do not create duplicate active actions for the same `agent_run_id` and generated action kind.
- Do not mutate learning routes, chapter status, mastery, or sessions.
- Do not expose raw prompts or full runtime payloads.

## Frontend Behavior

Study Space page:

- Add a `Create runtime actions` button in the planner actions panel.
- On success, replace/append the returned actions into the visible planner action list.
- Empty response shows a calm message: `No new runtime actions found.`

Chapter page:

- Add a `Create runtime actions` button in the review callout.
- Request includes `chapter_id`.
- Returned actions appear in the existing queued review actions list.

## Out of Scope

- Automatic action execution.
- Route mutation.
- New action types.
- Background jobs.
- LangGraph command routing.
