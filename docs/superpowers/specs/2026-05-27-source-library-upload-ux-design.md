# Source Library Upload UX Design

## Goal

Build the first frontend source-library loop inside a study space: upload a text or Markdown source, mark it uploaded, run runtime ingestion, list sources, and preview generated chunks.

## Dependency

This frontend phase depends on the runtime source ingestion backend being available on the target branch. The required backend endpoints are:

- `POST /api/v1/uploads/presign`
- `POST /api/v1/sources/{source_id}/uploaded`
- `GET /api/v1/study-spaces/{study_space_id}/sources`
- `POST /api/v1/ingestion/sources/{source_id}/run`
- `GET /api/v1/sources/{source_id}/chunks`

Implementation starts only after the backend runtime ingestion branch is merged into the working base.

## Scope

In scope:

- Extend `apps/web/pages/spaces/[id]/index.vue`.
- Add a source upload panel for `.txt` and `.md` files.
- Add source listing for the current study space.
- Add per-source actions to mark upload completion indirectly through the upload flow, run ingestion, and load chunks.
- Add a chunk preview panel for the selected source.
- Use development auth headers for protected backend calls.
- Add focused Vitest coverage for the visible controls and key states.

Out of scope:

- Full production login.
- PDF, image, OCR, webpage, and crawler upload UX.
- Drag-and-drop upload.
- Upload progress bars.
- Background job polling.
- Global source store abstraction.
- Full workspace tab redesign.
- RAG question-answer retrieval UI.
- Chinese copy cleanup across existing pages.

## Page Structure

The feature lives on the study space detail page:

`apps/web/pages/spaces/[id]/index.vue`

The page uses a two-column layout on desktop and a single-column stacked layout on narrow screens.

Top section:

- Page title: `Study Space`
- Subtitle: current route `spaceId`
- Inline alert area for upload, ingestion, and chunk-loading errors

Main content:

- Left column: source library
- Right column: chunk preview

## Source Library Column

The source library column contains an upload panel and a source list.

Upload panel elements:

- File input accepting `.txt,.md,text/plain,text/markdown`.
- Primary button labeled `Upload source`.
- Small helper text: `Supports .txt and .md. PDF, OCR, and webpage import will be added later.`

Upload behavior:

1. User selects a file.
2. Frontend validates file extension and MIME type when available.
3. User clicks `Upload source`.
4. Frontend calls `POST /uploads/presign` with:

```json
{
  "study_space_id": "<route space id>",
  "filename": "<file.name>",
  "content_type": "text/plain or text/markdown"
}
```

5. Frontend uploads the file body to `upload_url` with `PUT`.
6. Frontend calls `POST /sources/{source_id}/uploaded`.
7. Frontend reloads the source list.

Button states:

- Disabled when no file is selected.
- Disabled while uploading.
- Text changes to `Uploading...` while uploading.

Validation:

- `.md` maps to `text/markdown`.
- `.txt` maps to `text/plain`.
- Any other extension shows `This phase supports only .txt and .md files.`

## Source List

The source list loads from:

`GET /study-spaces/{study_space_id}/sources`

Each source row shows:

- Filename
- Content type
- Status badge
- Created time if available
- Error message if available

Status display:

- `pending_upload`: `Pending upload`
- `uploaded`: `Uploaded`
- `processing`: `Processing`
- `ready`: `Ready`
- `failed`: `Failed`
- Unknown values display as-is

Actions:

- `Run ingestion`: shown for `uploaded`, `ready`, and `failed`.
- `View chunks`: shown for all sources, disabled if no chunks are available after request.

Run ingestion behavior:

1. User clicks `Run ingestion`.
2. Frontend calls `POST /ingestion/sources/{source_id}/run`.
3. On success, reloads source list.
4. Then loads chunks for that source.

Button states:

- `Run ingestion` disables while the selected source is being ingested.
- The clicked row visually indicates it is active.

## Chunk Preview Column

Default state:

- Heading: `Chunk preview`
- Empty text: `Select a source to preview parsed chunks.`

Loading state:

- Text: `Loading chunks...`

Loaded state:

- Shows source filename.
- Shows chunk count.
- Lists chunks in order.

Chunk item elements:

- Header: `Chunk #<chunk_index>`
- Body: chunk text
- Footer: citation summary from `citation`, including page number when present

Empty chunks:

- Text: `This source has no chunks yet. Run ingestion first.`

## API Client Behavior

For this phase, API calls live inside `pages/spaces/[id]/index.vue` to keep the change local. The implementation defines small local helper functions instead of deeply nesting logic in event handlers.

All protected calls use development auth headers:

```ts
const DEV_AUTH_HEADERS = {
  'X-User-Id': '00000000-0000-0000-0000-000000000002',
  'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
}
```

The upload `PUT` to the presigned object URL does not include development auth headers. It includes the selected content type.

## Error Handling

The page has one visible error alert near the top of the content area.

Errors:

- Invalid file type: `This phase supports only .txt and .md files.`
- Presign failure: `Failed to create upload URL.`
- Object upload failure: `Failed to upload file to object storage.`
- Uploaded status failure: `Failed to confirm upload completion.`
- Source list failure: `Failed to load source list.`
- Ingestion failure: `Failed to run ingestion.`
- Chunk load failure: `Failed to load chunks.`

When a backend error includes a useful message, append it after the base message.

## Styling Direction

The UI matches the existing app style and stays utilitarian:

- Use existing `.topbar`, `.card`, and `.primary-button` patterns.
- Add scoped styles for two-column layout, status badges, rows, and chunk preview.
- Keep cards at `8px` radius to match the current system.
- Avoid decorative hero sections, gradients, and marketing composition.
- Ensure mobile layout stacks cleanly and buttons do not overflow.

## Testing

Add focused Vitest coverage under `apps/web/tests/`.

Minimum tests:

- The study space detail page renders the source upload control and upload button.
- The page renders a source list state when mocked sources are returned.
- The page renders a run-ingestion button for an uploaded source.
- The page renders the empty chunk preview state.

Mock network calls so tests do not require the backend server.

## Acceptance Criteria

- A user can select a `.txt` or `.md` file from a study space detail page.
- The frontend calls presign, uploads to object storage, marks the source uploaded, and refreshes sources.
- A user can run ingestion for an uploaded source.
- A user can view chunks for a source.
- Invalid file types are blocked before API calls.
- Protected API calls include development auth headers.
- The implementation is scoped to the study space detail page plus focused tests.
- Existing web tests continue to pass.
