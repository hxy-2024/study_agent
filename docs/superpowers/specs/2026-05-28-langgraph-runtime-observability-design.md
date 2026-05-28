# LangGraph Runtime Observability Design

## Purpose

Harden the current LangGraph foundation so graph-backed agents are easier to trace, debug, and later resume. This phase focuses on runtime metadata and checkpoint boundaries, not new product behavior.

The system already has a three-layer data loop:

```text
L3 Session Tutor -> L2 Chapter Mentor -> L1 Space Planner
```

The next production concern is operational: every graph run should have a stable thread identity, consistent metadata, node trace structure, and checkpoint backend declaration.

## Goals

- Standardize graph run metadata across successful and failed Session Tutor graph runs.
- Introduce a stable `thread_id` convention for graph execution.
- Add a checkpoint factory boundary with explicit support for `none`, `memory`, and reserved `postgres`.
- Keep the public API unchanged.
- Avoid requiring Postgres checkpoint tables in this phase.

## Non-Goals

- No SSE streaming.
- No background workers.
- No new database migrations.
- No new API endpoints.
- No automatic retry/resume behavior.
- No frontend changes.

## Runtime Metadata Contract

Every graph-backed Session Tutor `AgentRun` should include:

```json
{
  "graph_name": "session_tutor",
  "thread_id": "session:{session_id}",
  "checkpoint_backend": "memory",
  "state_schema_version": 1,
  "node_trace": ["load_session_context", "..."],
  "learning_signals": []
}
```

Success output payload should include:

- `assistant_message_id`
- `citation_count`
- `graph_name`
- `thread_id`
- `checkpoint_backend`
- `state_schema_version`
- `node_trace`
- `learning_signals`
- `chapter_supervision_used`

Failure input payload should include:

- `content`
- `user_message_id`
- `graph_name`
- `thread_id`
- `checkpoint_backend`
- `state_schema_version`
- `node_trace`

## Thread ID Strategy

Use a deterministic thread ID:

```text
session:{session_id}
```

This groups one tutoring session into a single graph thread. Later, if per-turn replay becomes necessary, a child run ID can be added without breaking this convention.

## Checkpoint Strategy

Supported configuration values:

- `none`: compile graph without a checkpointer.
- `memory`: use in-memory checkpointing for local/dev/test.
- `postgres`: reserved production option that fails closed until explicitly wired.

This phase should implement the factory boundary but does not need to create LangGraph Postgres checkpoint tables.

If `postgres` is requested before the project has a configured checkpoint database setup, the runtime should raise a clear `ValueError` rather than silently falling back.

## Testing Strategy

Unit tests should cover:

- stable thread ID generation
- graph metadata construction
- memory/no checkpoint backend handling
- postgres backend fail-closed behavior
- successful Session Tutor graph run records graph metadata
- failed Session Tutor graph run records graph metadata

Existing full API and web verification should continue passing.

## Acceptance Criteria

- `AgentRun.output_payload` for successful Session Tutor graph runs contains standardized graph metadata.
- failed Session Tutor graph runs contain the same graph metadata in `input_payload`.
- checkpoint backend config is explicit and validated.
- `postgres` checkpoint backend fails with a clear error until production setup is added.
- no route or frontend behavior changes.
