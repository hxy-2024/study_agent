# Source Library Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the study-space source library with status filters, clearer upload phases, retry/rerun actions, file metadata, and more precise empty states.

**Architecture:** Continue from `codex/source-library-upload-ux` and keep the implementation local to the study space detail page. The page owns filter state, upload phase state, selected file metadata, existing API helpers, source rows, and chunk preview state. Tests extend the existing `source-library.spec.ts` file and keep backend calls mocked.

**Tech Stack:** Nuxt 4, Vue 3 `<script setup>`, TypeScript, `$fetch`, Vitest, Vue Test Utils, happy-dom, scoped Vue CSS, `frontend-design` for refined utilitarian UI polish.

---

## Scope Check

This plan implements:

`docs/superpowers/specs/2026-05-27-source-library-polish-design.md`

Execution base:

`codex/source-library-upload-ux`

The working branch must include:

- `f6b30a1 feat: add source library upload page`
- `56186a3 fix: harden source upload interactions`

If the worktree reports Git dubious ownership, ask the user to run:

```powershell
git config --global --add safe.directory F:/AIproject/study_agent/.worktrees/codex-source-library-upload-ux
```

In scope:

- Modify `apps/web/pages/spaces/[id]/index.vue`.
- Modify `apps/web/tests/source-library.spec.ts`.
- Add filters, counts, action labels, upload phase display, selected file metadata, and empty-state improvements.

Out of scope:

- Backend changes.
- New stores or composables.
- Drag-and-drop uploads.
- Upload percentage progress.
- Background polling.
- Full workspace redesign.

## File Structure

```text
apps/web/
  pages/
    spaces/
      [id]/
        index.vue
  tests/
    source-library.spec.ts
```

Responsibilities:

- `apps/web/pages/spaces/[id]/index.vue`: page-local source library state, filter logic, upload phase state, refined actions, empty-state rendering, scoped styles.
- `apps/web/tests/source-library.spec.ts`: render and interaction tests for filters, upload phases, file metadata, retry/rerun labels, and preview empty-state action.

Implementation must use `frontend-design` with the chosen direction: refined utilitarian workspace, dense but calm, no hero section, no decorative blobs, no nested cards, buttons fitting on mobile.

---

### Task 1: Prepare Branch and Baseline

**Files:**
- Read: `apps/web/pages/spaces/[id]/index.vue`
- Read: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Enter the existing frontend worktree**

Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux
git branch --show-current
git log --oneline -5
```

Expected:

- Branch is `codex/source-library-upload-ux`.
- Log includes `56186a3` and `f6b30a1`.

- [ ] **Step 2: Fix safe.directory if needed**

If Git reports dubious ownership, run:

```powershell
git config --global --add safe.directory F:/AIproject/study_agent/.worktrees/codex-source-library-upload-ux
```

Then rerun:

```powershell
git status --short
```

Expected: status is readable. `apps/web/package-lock.json` may appear modified with empty `git diff`; do not stage it unless it has real content changes.

- [ ] **Step 3: Verify baseline tests**

Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux\apps\web
npm run test
```

Expected: existing tests pass.

Do not commit in this task.

---

### Task 2: Add Failing Polish Tests

**Files:**
- Modify: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Add helper for multiple sources**

In `apps/web/tests/source-library.spec.ts`, keep the existing `sourceItem` helper and add this helper below it:

```ts
function sourceListFixture() {
  return [
    sourceItem({
      id: '00000000-0000-0000-0000-000000000201',
      filename: 'uploaded.md',
      status: 'uploaded'
    }),
    sourceItem({
      id: '00000000-0000-0000-0000-000000000202',
      filename: 'ready.md',
      status: 'ready'
    }),
    sourceItem({
      id: '00000000-0000-0000-0000-000000000203',
      filename: 'failed.md',
      status: 'failed',
      error_message: 'Parser failed'
    }),
    sourceItem({
      id: '00000000-0000-0000-0000-000000000204',
      filename: 'processing.md',
      status: 'processing'
    })
  ]
}
```

- [ ] **Step 2: Append filter and action-label tests**

Append inside the existing `describe('StudySpacePage source library', () => { ... })` block:

```ts
  it('renders source status filters with counts', async () => {
    fetchMock.mockResolvedValueOnce({ sources: sourceListFixture() })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('All 4')
    expect(wrapper.text()).toContain('Uploaded 1')
    expect(wrapper.text()).toContain('Processing 1')
    expect(wrapper.text()).toContain('Ready 1')
    expect(wrapper.text()).toContain('Failed 1')
  })

  it('filters visible source rows by status', async () => {
    fetchMock.mockResolvedValueOnce({ sources: sourceListFixture() })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-filter="failed"]').trigger('click')

    expect(wrapper.text()).toContain('failed.md')
    expect(wrapper.text()).toContain('Parser failed')
    expect(wrapper.text()).not.toContain('uploaded.md')
    expect(wrapper.text()).not.toContain('ready.md')
  })

  it('shows retry and rerun labels for failed and ready sources', async () => {
    fetchMock.mockResolvedValueOnce({ sources: sourceListFixture() })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Retry ingestion')
    expect(wrapper.text()).toContain('Re-run ingestion')
  })
```

- [ ] **Step 3: Append upload phase and metadata tests**

Append inside the same `describe` block:

```ts
  it('shows selected file metadata before upload', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await selectFile(wrapper, new File(['# Notes'], 'notes.md', { type: 'text/markdown' }))

    expect(wrapper.text()).toContain('notes.md')
    expect(wrapper.text()).toContain('text/markdown')
    expect(wrapper.text()).toContain('7 B')
  })

  it('shows upload phase text while creating the upload URL', async () => {
    let resolvePresign: (value: unknown) => void = () => {}
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/uploads/presign')) {
        return new Promise(resolve => {
          resolvePresign = resolve
        })
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()
    await selectFile(wrapper, new File(['# Notes'], 'notes.md', { type: 'text/markdown' }))

    await wrapper.find('button.primary-button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Creating upload URL...')

    resolvePresign({
      source_id: '00000000-0000-0000-0000-000000000201',
      object_key: 'tenants/t/spaces/s/sources/source/notes.md',
      upload_url: 'http://object-storage.local/upload/notes.md',
      method: 'PUT'
    })
    await flushPromises()
  })

  it('keeps the selected file after upload failure', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/uploads/presign')) {
        return Promise.reject(new Error('No upload URL'))
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()
    await selectFile(wrapper, new File(['# Notes'], 'notes.md', { type: 'text/markdown' }))

    await wrapper.find('button.primary-button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('notes.md')
    expect(wrapper.text()).toContain('Failed to create upload URL. No upload URL')
  })
```

- [ ] **Step 4: Append preview empty-state action test**

Append inside the same `describe` block:

```ts
  it('shows preview-level run ingestion action when selected source has no chunks', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [sourceItem({ status: 'uploaded' })] })
      }
      if (url.endsWith('/sources/00000000-0000-0000-0000-000000000201/chunks')) {
        return Promise.resolve({ chunks: [] })
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button.secondary-button').find(button => button.text() === 'View chunks')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('This source has no chunks yet.')
    expect(wrapper.find('[data-testid="preview-run-ingestion"]').exists()).toBe(true)
  })
```

- [ ] **Step 5: Run tests to verify failure**

Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux\apps\web
npm run test -- tests/source-library.spec.ts
```

Expected: FAIL because filters, file metadata, phase text, and preview action do not exist yet.

Do not commit failing tests.

---

### Task 3: Implement Filter State and Source Action Labels

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Modify: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Add filter types and computed state**

In `apps/web/pages/spaces/[id]/index.vue`, below `type SourceStatus`, add:

```ts
type SourceFilter = 'all' | 'uploaded' | 'processing' | 'ready' | 'failed'
```

Below `const sources = ref<SourceItem[]>([])`, add:

```ts
const activeFilter = ref<SourceFilter>('all')
```

Below `const hasSelectedSource = computed(...)`, add:

```ts
const sourceFilters = computed(() => [
  { key: 'all' as const, label: 'All', count: sources.value.length },
  { key: 'uploaded' as const, label: 'Uploaded', count: sources.value.filter(source => source.status === 'uploaded').length },
  { key: 'processing' as const, label: 'Processing', count: sources.value.filter(source => source.status === 'processing').length },
  { key: 'ready' as const, label: 'Ready', count: sources.value.filter(source => source.status === 'ready').length },
  { key: 'failed' as const, label: 'Failed', count: sources.value.filter(source => source.status === 'failed').length }
])

const filteredSources = computed(() => {
  if (activeFilter.value === 'all') return sources.value
  return sources.value.filter(source => source.status === activeFilter.value)
})
```

- [ ] **Step 2: Add action label helper**

Below `function canRunIngestion(source: SourceItem)`, add:

```ts
function ingestionActionLabel(source: SourceItem) {
  if (source.status === 'failed') return 'Retry ingestion'
  if (source.status === 'ready') return 'Re-run ingestion'
  return 'Run ingestion'
}
```

- [ ] **Step 3: Render filter bar**

In the source list card, after the section heading and before loading/empty source states, add:

```vue
          <div class="filter-bar" aria-label="Source status filters">
            <button
              v-for="filter in sourceFilters"
              :key="filter.key"
              type="button"
              class="filter-button"
              :class="{ active: activeFilter === filter.key }"
              :data-filter="filter.key"
              @click="activeFilter = filter.key"
            >
              <span>{{ filter.label }}</span>
              <strong>{{ filter.count }}</strong>
            </button>
          </div>
```

- [ ] **Step 4: Use filtered sources in template**

Change:

```vue
          <p v-else-if="sources.length === 0" class="empty-state">No sources yet. Upload a Markdown or text file to start.</p>

          <div v-else class="source-list">
            <article
              v-for="source in sources"
```

to:

```vue
          <p v-else-if="sources.length === 0" class="empty-state">No sources yet. Upload a Markdown or text file to start.</p>
          <p v-else-if="filteredSources.length === 0" class="empty-state">No sources match this filter.</p>

          <div v-else class="source-list">
            <article
              v-for="source in filteredSources"
```

- [ ] **Step 5: Use action labels**

Change ingestion button text:

```vue
{{ ingestingSourceId === source.id ? 'Running...' : 'Run ingestion' }}
```

to:

```vue
{{ ingestingSourceId === source.id ? 'Running...' : ingestionActionLabel(source) }}
```

- [ ] **Step 6: Add filter styles**

Add to the scoped style block:

```css
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-button {
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 6px 10px;
}

.filter-button strong {
  border-radius: 999px;
  background: #e2e8f0;
  color: #172033;
  font-size: 12px;
  line-height: 1;
  padding: 4px 6px;
}

.filter-button.active {
  border-color: #2563eb;
  color: #1d4ed8;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}
```

- [ ] **Step 7: Run tests**

Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux\apps\web
npm run test -- tests/source-library.spec.ts
```

Expected: filter/action tests PASS; upload metadata/phase and preview action tests still FAIL.

Do not commit yet.

---

### Task 4: Implement Upload Phase and File Metadata

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Modify: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Add upload phase type and state**

Below `type SourceFilter`, add:

```ts
type UploadPhase = 'idle' | 'creating_url' | 'uploading_file' | 'confirming_upload' | 'refreshing_sources'
```

Replace:

```ts
const uploading = ref(false)
```

with:

```ts
const uploadPhase = ref<UploadPhase>('idle')
```

Replace:

```ts
const canUpload = computed(() => selectedFile.value !== null && !uploading.value)
```

with:

```ts
const uploading = computed(() => uploadPhase.value !== 'idle')
const canUpload = computed(() => selectedFile.value !== null && !uploading.value)
```

- [ ] **Step 2: Add file metadata computed state**

Below `const filteredSources = computed(...)`, add:

```ts
const inferredContentType = computed(() => {
  if (!selectedFile.value) return ''
  return contentTypeForFile(selectedFile.value) ?? 'Unsupported'
})

const selectedFileSize = computed(() => {
  if (!selectedFile.value) return ''
  return formatFileSize(selectedFile.value.size)
})

const uploadPhaseLabel = computed(() => {
  const labels: Record<UploadPhase, string> = {
    idle: 'Upload source',
    creating_url: 'Creating upload URL...',
    uploading_file: 'Uploading file...',
    confirming_upload: 'Confirming upload...',
    refreshing_sources: 'Refreshing sources...'
  }
  return labels[uploadPhase.value]
})
```

- [ ] **Step 3: Add file size helper**

Below `function contentTypeForFile(file: File)`, add:

```ts
function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  const kib = bytes / 1024
  if (kib < 1024) return `${kib.toFixed(1)} KB`
  return `${(kib / 1024).toFixed(1)} MB`
}
```

- [ ] **Step 4: Set upload phases**

In `uploadSource`, replace:

```ts
  uploading.value = true
  errorMessage.value = ''
  let uploadErrorMessage = 'Failed to create upload URL.'
  try {
```

with:

```ts
  uploadPhase.value = 'creating_url'
  errorMessage.value = ''
  let uploadErrorMessage = 'Failed to create upload URL.'
  try {
```

Before object upload, set:

```ts
    uploadPhase.value = 'uploading_file'
```

Before uploaded confirmation, set:

```ts
    uploadPhase.value = 'confirming_upload'
```

Before `await loadSources()`, set:

```ts
    uploadPhase.value = 'refreshing_sources'
```

In `finally`, replace:

```ts
    uploading.value = false
```

with:

```ts
    uploadPhase.value = 'idle'
```

- [ ] **Step 5: Render selected file metadata and phase text**

Replace the upload actions block:

```vue
          <div class="upload-actions">
            <span class="selected-file">{{ selectedFile?.name || 'No file selected' }}</span>
            <button class="primary-button" type="button" :disabled="!canUpload" @click="uploadSource">
              {{ uploading ? 'Uploading...' : 'Upload source' }}
            </button>
          </div>
```

with:

```vue
          <div class="selected-file-panel">
            <p class="selected-file">{{ selectedFile?.name || 'No file selected' }}</p>
            <dl v-if="selectedFile" class="file-meta">
              <div>
                <dt>Type</dt>
                <dd>{{ inferredContentType }}</dd>
              </div>
              <div>
                <dt>Size</dt>
                <dd>{{ selectedFileSize }}</dd>
              </div>
            </dl>
            <p v-if="uploading" class="upload-phase">{{ uploadPhaseLabel }}</p>
          </div>

          <div class="upload-actions">
            <button class="primary-button" type="button" :disabled="!canUpload" @click="uploadSource">
              {{ uploadPhaseLabel }}
            </button>
          </div>
```

- [ ] **Step 6: Add file metadata styles**

Add to scoped styles:

```css
.selected-file-panel {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 12px;
}

.file-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 10px 0 0;
}

.file-meta div {
  min-width: 0;
}

.file-meta dt {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.file-meta dd {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
}

.upload-phase {
  color: #1d4ed8;
  font-weight: 700;
  margin: 10px 0 0;
}
```

- [ ] **Step 7: Run tests**

Run:

```powershell
npm run test -- tests/source-library.spec.ts
```

Expected: filter/action/upload metadata/phase tests PASS; preview empty action test still FAIL.

Do not commit yet.

---

### Task 5: Implement Chunk Empty-State Action

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Modify: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Add selected source run helper**

Below `async function runIngestion(source: SourceItem)`, add:

```ts
async function runSelectedSourceIngestion() {
  if (!selectedSource.value || !canRunIngestion(selectedSource.value)) return
  await runIngestion(selectedSource.value)
}
```

- [ ] **Step 2: Replace empty chunks preview block**

Replace:

```vue
        <div v-else-if="chunks.length === 0" class="empty-state">This source has no chunks yet. Run ingestion first.</div>
```

with:

```vue
        <div v-else-if="chunks.length === 0" class="empty-state preview-empty">
          <p>This source has no chunks yet.</p>
          <button
            v-if="selectedSource && canRunIngestion(selectedSource)"
            data-testid="preview-run-ingestion"
            type="button"
            class="secondary-button"
            :disabled="ingestingSourceId === selectedSource.id"
            @click="runSelectedSourceIngestion"
          >
            {{ ingestingSourceId === selectedSource.id ? 'Running...' : ingestionActionLabel(selectedSource) }}
          </button>
        </div>
```

- [ ] **Step 3: Add preview empty style**

Add to scoped styles:

```css
.preview-empty {
  display: grid;
  gap: 12px;
  justify-items: start;
}
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
npm run test -- tests/source-library.spec.ts
```

Expected: all `source-library.spec.ts` tests PASS.

- [ ] **Step 5: Commit polish implementation**

```powershell
git add apps/web/pages/spaces/[id]/index.vue apps/web/tests/source-library.spec.ts
git commit -m "feat: polish source library workspace"
```

---

### Task 6: Final Verification and Visual Review

**Files:**
- Read: `apps/web/pages/spaces/[id]/index.vue`
- Read: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Run full tests**

Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux\apps\web
npm run test
```

Expected: all Vitest tests PASS.

- [ ] **Step 2: Run typecheck**

Run:

```powershell
npm run typecheck
```

Expected: exit code 0. Existing Vue language plugin warnings can be recorded if no TypeScript errors are emitted.

- [ ] **Step 3: Run production build**

Run:

```powershell
npm run build
```

Expected: exit code 0. Existing Nuxt sourcemap or deprecation warnings can be recorded if build completes.

- [ ] **Step 4: Browser visual check**

Start the dev server manually if tool sandbox blocks background processes:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux\apps\web
npm run dev -- --host 127.0.0.1 --port 3010
```

Open:

`http://127.0.0.1:3010/spaces/00000000-0000-0000-0000-000000000101`

Verify:

- Filter bar fits on desktop and wraps on mobile.
- Upload metadata panel does not overflow.
- Source row buttons fit on desktop and stack on mobile.
- Chunk preview empty action is visible and not cramped.
- No decorative hero, no nested cards, no text overlap.

- [ ] **Step 5: Commit visual polish if needed**

If visual review requires CSS fixes, commit only those fixes:

```powershell
git add apps/web/pages/spaces/[id]/index.vue
git commit -m "fix: polish source library responsive layout"
```

If no CSS fixes are needed, do not create an empty commit.

## Final Verification

Before PR update, record:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux\apps\web
npm run test
npm run typecheck
npm run build
```

Expected:

- Vitest passes.
- Typecheck exits 0.
- Build exits 0.

## Execution Order

1. Continue from `codex/source-library-upload-ux`.
2. Execute Tasks 1-6 in order.
3. Push the updated branch.
4. Update the existing PR for `codex/source-library-upload-ux`.

## Self-Review

- Spec coverage: filters, counts, retry/rerun labels, upload phases, selected file metadata, failure retention, and empty states are all mapped to tasks.
- Scope control: only the detail page and its test file are modified.
- Type consistency: `SourceFilter`, `UploadPhase`, `SourceItem`, and existing helper names match the current page structure.
- Frontend-design alignment: plan keeps a dense utilitarian workspace, scoped styles, no hero, no decorative blobs, no nested cards, and explicit mobile-fit checks.
