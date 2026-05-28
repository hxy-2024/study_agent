# Chapter Mentor Learning Signals Design

## Purpose

Connect the L3 Session Tutor graph to the L2 Chapter Mentor by making Chapter Mentor state generation consume `learning_signals` recorded in Session Tutor `agent_runs.output_payload`.

This phase turns the three-layer agent architecture from a reserved interface into a working upward feedback loop:

```text
L3 Session Tutor -> learning_signals -> L2 Chapter Mentor state
```

## Current State

Session Tutor graph runs now record `AgentRun` rows with:

- `agent_type=session_tutor`
- `session_id`
- `output_payload.learning_signals`
- `output_payload.node_trace`
- `output_payload.chapter_supervision_used`

Chapter Mentor state generation currently reads chapter messages and produces:

- `summary`
- `weak_points`
- `next_actions`
- `evidence`
- source session/message counts

It does not yet consume Session Tutor learning signals.

## Design

Update `generate_chapter_mentor_state()` so it reads completed Session Tutor agent runs for the chapter's sessions and folds their learning signals into the state.

Signal handling rules:

- `confusion_detected=true` adds a weak point describing recent learner confusion.
- `needs_review=true` adds a next action recommending a focused review.
- `evidence_used=false` adds a weak point about insufficient cited evidence.
- `chapter_supervision_used=true` is recorded as evidence, not as a weak point.

The Chapter Mentor remains deterministic. It does not call an LLM in this phase.

## Scope

Implement:

- Query completed Session Tutor `AgentRun` rows joined through `Session`.
- Extract `learning_signals` from `AgentRun.output_payload`.
- Include compact signal evidence in `ChapterMentorState.evidence`.
- Use signals to enrich `weak_points` and `next_actions`.
- Add unit tests for signal extraction and state generation.

Do not implement:

- New database tables.
- New API endpoints.
- Frontend changes.
- Space Planner signal aggregation.
- Automatic planner action creation.

## Acceptance Criteria

- Chapter Mentor state generation still works when no Session Tutor signals exist.
- When Session Tutor signals exist, `weak_points`, `next_actions`, and `evidence` reflect them.
- Existing Chapter Mentor route behavior remains unchanged.
- Existing API tests continue to pass.
