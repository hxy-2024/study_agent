# Supervision Freshness Design

## Problem

The project already has a three-layer learning agent shape:

- L1 Space Planner monitors the study space.
- L2 Chapter Mentor summarizes chapter-level weak points and next actions.
- L3 Session Tutor helps inside a tutoring session and records `learning_signals`.

The missing production behavior is freshness. After L3 records new completed tutor signals, the UI does not clearly tell the learner whether L2 has already consumed those signals or whether the chapter mentor assessment should be refreshed.

## Decision

Add a computed, read-only supervision freshness model. Do not add a migration and do not mark signals as processed yet.

The backend compares:

- latest completed `session_tutor` `AgentRun.completed_at` or `created_at` for a chapter
- current `ChapterMentorState.updated_at`

If a chapter has a newer completed tutor run than its mentor state, the chapter is `needs_supervision_refresh=true`.

## UX

Chapter page:

- Show a compact callout in the mentor assessment area when new tutor signals need L2 assessment.
- The existing `Update assessment` button remains the user-confirmed action.

Study space page:

- When Space Planner state is available, show a small "supervision refresh" count based on planner evidence.
- Each planner evidence row can include whether the chapter has stale supervision.

## Non-goals

- No background worker.
- No automatic route mutation.
- No new database table.
- No exact once-only signal acknowledgement yet.
