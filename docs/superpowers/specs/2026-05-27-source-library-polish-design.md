# Source Library Polish Design

## Goal

Improve the existing study-space source library from a working upload/ingestion loop into a more usable production-style workspace surface with filtering, clearer upload progress, retry actions, and better empty states.

## Base Branch

This phase builds on:

`codex/source-library-upload-ux`

The implementation should continue from that branch or from a branch that already includes its two commits:

- `f6b30a1 feat: add source library upload page`
- `56186a3 fix: harden source upload interactions`

## Scope

In scope:

- Keep work focused on `apps/web/pages/spaces/[id]/index.vue`.
- Extend existing `apps/web/tests/source-library.spec.ts`.
- Add source status filters with counts.
- Add clearer retry and rerun actions for failed and ready sources.
- Add upload phase messaging.
- Show selected file metadata before upload.
- Improve source-list empty states and chunk-preview empty states.
- Preserve development auth behavior from the previous phase.
- Preserve current backend API contracts.

Out of scope:

- New backend endpoints.
- Polling ingestion jobs in the background.
- Drag-and-drop upload.
- Upload progress percentage from object storage.
- PDF/OCR/web import.
- Global source store extraction.
- Full workspace tab redesign.
- Production login.

## UX Direction

Use the `frontend-design` skill during implementation, with a refined utilitarian workspace direction:

- Dense enough for repeated work.
- Clear visual hierarchy between filters, source rows, and chunk preview.
- Quiet colors, strong status semantics, no decorative hero or marketing layout.
- Buttons and labels must fit on mobile.
- No nested cards.
- Scoped styles only.

## Source Filters

Add a compact filter bar above the source list.

Filters:

- `All`
- `Uploaded`
- `Processing`
- `Ready`
- `Failed`

Each filter shows a count based on the loaded `sources` array.

Behavior:

- Default filter is `All`.
- Clicking a filter updates the visible source rows.
- If a filter has no matching sources, show `No sources match this filter.`
- Counts update after upload, ingestion, and refresh.

Status mapping:

- `uploaded` counts under `Uploaded`
- `processing` counts under `Processing`
- `ready` counts under `Ready`
- `failed` counts under `Failed`
- Other statuses appear under `All` only

## Source Row Actions

Action labels:

- `uploaded`: `Run ingestion`
- `failed`: `Retry ingestion`
- `ready`: `Re-run ingestion`
- `processing`: no ingestion button
- `pending_upload`: no ingestion button

Behavior:

- Clicking any ingestion action calls the existing runtime ingestion endpoint.
- While a source is ingesting, only that source row action is disabled and displays `Running...`.
- Failed source rows keep showing their `error_message`.
- Ready source rows retain `View chunks`.

## Upload Experience

Selected file metadata:

- Filename
- Human-readable file size
- Inferred content type

Upload phase state:

- `idle`
- `creating_url`
- `uploading_file`
- `confirming_upload`
- `refreshing_sources`

Visible messages:

- `creating_url`: `Creating upload URL...`
- `uploading_file`: `Uploading file...`
- `confirming_upload`: `Confirming upload...`
- `refreshing_sources`: `Refreshing sources...`

Button behavior:

- Button text mirrors the current phase when uploading.
- Upload button is disabled while any upload phase is active.
- If upload fails, keep the selected file so the user can retry.
- If upload succeeds, clear the selected file.

Validation:

- Keep current extension and MIME validation.
- Keep current invalid file error message.

## Empty States

Source list:

- No sources at all: `No sources yet. Upload a Markdown or text file to start.`
- Active filter has no matches: `No sources match this filter.`
- Loading sources: `Loading sources...`

Chunk preview:

- No selected source: `Select a source to preview parsed chunks.`
- Selected source has no chunks:
  - Text: `This source has no chunks yet.`
  - If the source can run ingestion, show a small `Run ingestion` action in the preview.
- Loading chunks: `Loading chunks...`

## Error Handling

Keep existing error messages and add no new backend assumptions.

Existing messages remain:

- `This phase supports only .txt and .md files.`
- `Failed to create upload URL.`
- `Failed to upload file to object storage.`
- `Failed to confirm upload completion.`
- `Failed to load source list.`
- `Failed to run ingestion.`
- `Failed to load chunks.`

## Testing

Extend `apps/web/tests/source-library.spec.ts`.

Minimum new tests:

- Renders filter buttons with counts.
- Filters visible source rows by status.
- Shows `Retry ingestion` for failed sources and `Re-run ingestion` for ready sources.
- Displays selected file metadata before upload.
- Shows upload phase text during upload.
- Keeps selected file after upload failure.
- Shows preview-level `Run ingestion` action when selected source has no chunks and can run ingestion.

Existing tests from the previous phase must continue to pass.

## Acceptance Criteria

- Source list supports All/Uploaded/Processing/Ready/Failed filtering with counts.
- Failed sources expose retry wording.
- Ready sources expose rerun wording.
- Upload panel shows file metadata and phase-specific progress text.
- Upload failure keeps the selected file for retry.
- Empty states distinguish no sources, no filter matches, no selected source, and selected source with no chunks.
- Existing upload, ingestion, and chunk preview behavior remains intact.
- `npm run test`, `npm run typecheck`, and `npm run build` pass.
