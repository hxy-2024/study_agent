# Source Library Upload UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first Nuxt source-library loop on the study space detail page: upload text/Markdown, run ingestion, list sources, and preview chunks.

**Architecture:** Keep this phase local to the study space detail page instead of creating a global store. The page owns small typed API helpers, development auth headers, upload state, source-list state, ingestion state, and chunk-preview state. Styling stays scoped and follows the existing app shell while applying the `frontend-design` skill for a refined, utilitarian workspace UI.

**Tech Stack:** Nuxt 4, Vue 3 `<script setup>`, TypeScript, `$fetch`, Pinia-adjacent existing app structure, Vitest, Vue Test Utils, happy-dom.

---

## Scope Check

This plan implements the confirmed spec:

`docs/superpowers/specs/2026-05-27-source-library-upload-ux-design.md`

Execution depends on the backend runtime ingestion branch being merged first:

`codex/runtime-source-ingestion`

Do not start the implementation task until `main` contains these backend routes:

- `GET /api/v1/study-spaces/{study_space_id}/sources`
- `POST /api/v1/uploads/presign`
- `POST /api/v1/sources/{source_id}/uploaded`
- `POST /api/v1/ingestion/sources/{source_id}/run`
- `GET /api/v1/sources/{source_id}/chunks`

If the merge is not present, stop and ask the user to run:

```powershell
cd F:\AIproject\study_agent
git merge --no-ff codex/runtime-source-ingestion -m "merge: runtime source ingestion"
```

In scope:

- Extend `apps/web/pages/spaces/[id]/index.vue`.
- Add focused page tests in `apps/web/tests/source-library.spec.ts`.
- Use dev auth headers in protected API calls.
- Keep upload `PUT` free of dev auth headers.
- Verify with Vitest and a local Nuxt browser check.

Out of scope:

- Production auth.
- PDF/OCR/web import UI.
- Upload progress bars.
- Background polling.
- Global source store abstraction.
- RAG retrieval UI.
- Full workspace tab redesign.
- Existing mojibake copy cleanup outside the touched detail page.

## File Structure

Files to modify or create:

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

- `apps/web/pages/spaces/[id]/index.vue`: local source-library UI, API helpers, upload flow, ingestion flow, chunk preview, scoped styles.
- `apps/web/tests/source-library.spec.ts`: page rendering and state tests with mocked `$fetch`, `useRuntimeConfig`, and `useRoute`.

Implementation stage must use `frontend-design` to keep the detail page polished, dense, and production-grade without turning it into a marketing layout.

---

### Task 1: Verify Backend Prerequisite and Create Frontend Worktree

**Files:**
- Read: `apps/api/app/api/router.py`
- Read: `apps/api/app/api/routes_sources.py`
- Read: `apps/api/app/api/routes_ingestion.py`
- Read: `docs/superpowers/specs/2026-05-27-source-library-upload-ux-design.md`

- [ ] **Step 1: Verify backend routes exist**

Run from repo root:

```powershell
rg -n "routes_sources|create_runtime_text_source_reader|get_authorized_user_context|sources/.+uploaded|study-spaces/.+sources" apps/api/app
```

Expected: output includes `routes_sources`, `create_runtime_text_source_reader`, and source-library route definitions.

- [ ] **Step 2: Stop if backend branch is missing**

If Step 1 does not show the runtime source ingestion backend, stop and ask the user to run:

```powershell
cd F:\AIproject\study_agent
git merge --no-ff codex/runtime-source-ingestion -m "merge: runtime source ingestion"
```

Expected after the user runs it: `git log --oneline -3` shows a merge commit newer than the source-library design commit.

- [ ] **Step 3: Create isolated worktree**

Run from repo root:

```powershell
git worktree add .worktrees/codex-source-library-upload-ux -b codex/source-library-upload-ux
```

Expected: worktree created at `F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux`.

If sandbox blocks this, ask the user to run the same command manually.

- [ ] **Step 4: Verify web baseline**

Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux\apps\web
npm run test
```

Expected: existing Vitest suite passes.

Do not commit in this task.

---

### Task 2: Add Failing Source Library Page Tests

**Files:**
- Create: `apps/web/tests/source-library.spec.ts`
- Read: `apps/web/pages/spaces/[id]/index.vue`

- [ ] **Step 1: Create focused failing tests**

Create `apps/web/tests/source-library.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StudySpacePage from '../pages/spaces/[id]/index.vue'

const fetchMock = vi.fn()

vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRoute', () => ({
  params: {
    id: '00000000-0000-0000-0000-000000000101'
  }
}))

function mountPage() {
  return mount(StudySpacePage, {
    global: {
      stubs: {
        NuxtLink: true
      }
    }
  })
}

describe('StudySpacePage source library', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({ sources: [] })
  })

  it('renders the source upload control and upload button', async () => {
    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Source library')
    expect(wrapper.find('input[type="file"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Upload source')
  })

  it('renders source rows returned by the API', async () => {
    fetchMock.mockResolvedValueOnce({
      sources: [
        {
          id: '00000000-0000-0000-0000-000000000201',
          tenant_id: '00000000-0000-0000-0000-000000000001',
          study_space_id: '00000000-0000-0000-0000-000000000101',
          filename: 'intro.md',
          content_type: 'text/markdown',
          object_key: 'tenants/t/spaces/s/sources/source/intro.md',
          status: 'uploaded',
          error_message: null,
          created_at: '2026-05-27T00:00:00Z'
        }
      ]
    })

    const wrapper = mountPage()
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(wrapper.text()).toContain('intro.md')
    expect(wrapper.text()).toContain('Uploaded')
    expect(wrapper.text()).toContain('Run ingestion')
  })

  it('renders the empty chunk preview state', async () => {
    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Chunk preview')
    expect(wrapper.text()).toContain('Select a source to preview parsed chunks.')
  })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run from `apps/web`:

```powershell
npm run test -- source-library.spec.ts
```

Expected: FAIL because the current page does not render source-library controls.

- [ ] **Step 3: Leave failing tests uncommitted**

Expected: `git status --short` shows `apps/web/tests/source-library.spec.ts` as an uncommitted new file. Commit it together with the implementation in Task 4 after tests pass.

---

### Task 3: Implement Local API Helpers and Page State

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Test: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Replace script block with typed state and API helpers**

Modify `apps/web/pages/spaces/[id]/index.vue` script block:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type SourceStatus = 'pending_upload' | 'uploaded' | 'processing' | 'ready' | 'failed' | string

interface SourceItem {
  id: string
  tenant_id: string
  study_space_id: string
  filename: string
  content_type: string
  object_key: string
  status: SourceStatus
  error_message: string | null
  created_at: string | null
}

interface SourceListResponse {
  sources: SourceItem[]
}

interface UploadPresignResponse {
  source_id: string
  object_key: string
  upload_url: string
  method: string
}

interface SourceChunk {
  id: string
  source_id: string
  chunk_index: number
  text: string
  citation: Record<string, unknown>
}

interface SourceChunkListResponse {
  chunks: SourceChunk[]
}

const DEV_AUTH_HEADERS = {
  'X-User-Id': '00000000-0000-0000-0000-000000000002',
  'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
}

const route = useRoute()
const config = useRuntimeConfig()
const spaceId = computed(() => String(route.params.id))

const sources = ref<SourceItem[]>([])
const selectedFile = ref<File | null>(null)
const selectedSourceId = ref<string | null>(null)
const selectedSourceName = ref('')
const chunks = ref<SourceChunk[]>([])
const chunklessSourceIds = ref<Set<string>>(new Set())
const loadingSources = ref(false)
const uploading = ref(false)
const ingestingSourceId = ref<string | null>(null)
const loadingChunks = ref(false)
const errorMessage = ref('')

const canUpload = computed(() => selectedFile.value !== null && !uploading.value)
const selectedSource = computed(() => sources.value.find(source => source.id === selectedSourceId.value) ?? null)

function protectedHeaders() {
  return DEV_AUTH_HEADERS
}

function formatStatus(status: SourceStatus) {
  const labels: Record<string, string> = {
    pending_upload: 'Pending upload',
    uploaded: 'Uploaded',
    processing: 'Processing',
    ready: 'Ready',
    failed: 'Failed'
  }
  return labels[status] ?? status
}

function canRunIngestion(source: SourceItem) {
  return ['uploaded', 'ready', 'failed'].includes(source.status)
}

function contentTypeForFile(file: File) {
  const lowerName = file.name.toLowerCase()
  if (lowerName.endsWith('.md')) return 'text/markdown'
  if (lowerName.endsWith('.txt')) return 'text/plain'
  return null
}

function citationSummary(citation: Record<string, unknown>) {
  const page = citation.page_number ?? citation.page
  if (page) return `Page ${page}`
  return Object.keys(citation).length ? JSON.stringify(citation) : 'No citation metadata'
}

function appendBackendMessage(base: string, error: unknown) {
  if (error instanceof Error && error.message) return `${base} ${error.message}`
  return base
}

function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
  errorMessage.value = ''
}

async function loadSources() {
  loadingSources.value = true
  errorMessage.value = ''
  try {
    const response = await $fetch<SourceListResponse>(
      `${config.public.apiBaseUrl}/study-spaces/${spaceId.value}/sources`,
      { headers: protectedHeaders() }
    )
    sources.value = response.sources
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to load source list.', error)
  } finally {
    loadingSources.value = false
  }
}

async function uploadSource() {
  if (!selectedFile.value) return
  const contentType = contentTypeForFile(selectedFile.value)
  if (!contentType) {
    errorMessage.value = 'This phase supports only .txt and .md files.'
    return
  }

  uploading.value = true
  errorMessage.value = ''
  try {
    const presign = await $fetch<UploadPresignResponse>(`${config.public.apiBaseUrl}/uploads/presign`, {
      method: 'POST',
      headers: protectedHeaders(),
      body: {
        study_space_id: spaceId.value,
        filename: selectedFile.value.name,
        content_type: contentType
      }
    })

    await $fetch(presign.upload_url, {
      method: 'PUT',
      headers: {
        'Content-Type': contentType
      },
      body: selectedFile.value
    })

    await $fetch(`${config.public.apiBaseUrl}/sources/${presign.source_id}/uploaded`, {
      method: 'POST',
      headers: protectedHeaders()
    })

    selectedFile.value = null
    await loadSources()
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to upload source.', error)
  } finally {
    uploading.value = false
  }
}

async function runIngestion(source: SourceItem) {
  ingestingSourceId.value = source.id
  selectedSourceId.value = source.id
  selectedSourceName.value = source.filename
  errorMessage.value = ''
  try {
    await $fetch(`${config.public.apiBaseUrl}/ingestion/sources/${source.id}/run`, {
      method: 'POST',
      headers: protectedHeaders()
    })
    await loadSources()
    await loadChunks(source)
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to run ingestion.', error)
  } finally {
    ingestingSourceId.value = null
  }
}

async function loadChunks(source: SourceItem) {
  selectedSourceId.value = source.id
  selectedSourceName.value = source.filename
  loadingChunks.value = true
  errorMessage.value = ''
  try {
    const response = await $fetch<SourceChunkListResponse>(
      `${config.public.apiBaseUrl}/sources/${source.id}/chunks`,
      { headers: protectedHeaders() }
    )
    chunks.value = response.chunks
    if (response.chunks.length === 0) {
      chunklessSourceIds.value = new Set([...chunklessSourceIds.value, source.id])
    } else {
      const nextChunklessIds = new Set(chunklessSourceIds.value)
      nextChunklessIds.delete(source.id)
      chunklessSourceIds.value = nextChunklessIds
    }
  } catch (error) {
    chunks.value = []
    errorMessage.value = appendBackendMessage('Failed to load chunks.', error)
  } finally {
    loadingChunks.value = false
  }
}

onMounted(() => {
  loadSources()
})
</script>
```

- [ ] **Step 2: Run tests to verify script compiles but UI still fails**

Run from `apps/web`:

```powershell
npm run test -- source-library.spec.ts
```

Expected: tests still FAIL until the template renders the source library.

Do not commit in this task; commit after Task 4 renders the UI.

---

### Task 4: Implement Source Library and Chunk Preview UI

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Test: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Replace template block**

Modify `apps/web/pages/spaces/[id]/index.vue` template block:

```vue
<template>
  <section>
    <div class="topbar">
      <div>
        <h1>Study Space</h1>
        <p>Space ID: {{ spaceId }}</p>
      </div>
    </div>

    <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>

    <div class="workspace-grid">
      <div class="source-column">
        <section class="card source-upload-card">
          <div>
            <p class="eyebrow">Source library</p>
            <h2>Upload learning material</h2>
            <p class="muted">Supports .txt and .md. PDF, OCR, and webpage import will be added later.</p>
          </div>

          <label class="file-picker">
            <span>Choose source file</span>
            <input type="file" accept=".txt,.md,text/plain,text/markdown" @change="onFileSelected">
          </label>

          <div class="upload-actions">
            <span class="selected-file">{{ selectedFile?.name || 'No file selected' }}</span>
            <button class="primary-button" type="button" :disabled="!canUpload" @click="uploadSource">
              {{ uploading ? 'Uploading...' : 'Upload source' }}
            </button>
          </div>
        </section>

        <section class="card source-list-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Sources</p>
              <h2>Study materials</h2>
            </div>
            <button type="button" class="secondary-button" :disabled="loadingSources" @click="loadSources">
              Refresh
            </button>
          </div>

          <p v-if="loadingSources" class="muted">Loading sources...</p>
          <p v-else-if="sources.length === 0" class="empty-state">No sources yet. Upload a Markdown or text file to start.</p>

          <div v-else class="source-list">
            <article
              v-for="source in sources"
              :key="source.id"
              class="source-row"
              :class="{ active: selectedSourceId === source.id }"
            >
              <div class="source-main">
                <div>
                  <h3>{{ source.filename }}</h3>
                  <p>{{ source.content_type }}</p>
                </div>
                <span class="status-badge" :data-status="source.status">{{ formatStatus(source.status) }}</span>
              </div>

              <p v-if="source.error_message" class="source-error">{{ source.error_message }}</p>
              <p v-if="source.created_at" class="source-meta">Created {{ new Date(source.created_at).toLocaleString() }}</p>

              <div class="row-actions">
                <button
                  v-if="canRunIngestion(source)"
                  type="button"
                  class="secondary-button"
                  :disabled="ingestingSourceId === source.id"
                  @click="runIngestion(source)"
                >
                  {{ ingestingSourceId === source.id ? 'Running...' : 'Run ingestion' }}
                </button>
                <button
                  type="button"
                  class="secondary-button"
                  :disabled="chunklessSourceIds.has(source.id)"
                  @click="loadChunks(source)"
                >
                  View chunks
                </button>
              </div>
            </article>
          </div>
        </section>
      </div>

      <aside class="card chunk-preview">
        <div class="section-heading">
          <div>
            <p class="eyebrow">RAG preview</p>
            <h2>Chunk preview</h2>
          </div>
          <span v-if="chunks.length" class="chunk-count">{{ chunks.length }} chunks</span>
        </div>

        <p v-if="loadingChunks" class="muted">Loading chunks...</p>
        <div v-else-if="!selectedSource" class="empty-state">Select a source to preview parsed chunks.</div>
        <div v-else-if="chunks.length === 0" class="empty-state">This source has no chunks yet. Run ingestion first.</div>
        <div v-else class="chunk-list">
          <p class="selected-source-name">{{ selectedSourceName }}</p>
          <article v-for="chunk in chunks" :key="chunk.id" class="chunk-card">
            <h3>Chunk #{{ chunk.chunk_index }}</h3>
            <p>{{ chunk.text }}</p>
            <small>{{ citationSummary(chunk.citation) }}</small>
          </article>
        </div>
      </aside>
    </div>
  </section>
</template>
```

- [ ] **Step 2: Add scoped styles**

Append to `apps/web/pages/spaces/[id]/index.vue`:

```vue
<style scoped>
.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.9fr);
  gap: 18px;
  align-items: start;
}

.source-column {
  display: grid;
  gap: 18px;
}

.source-upload-card,
.source-list-card,
.chunk-preview {
  display: grid;
  gap: 16px;
}

.eyebrow {
  margin: 0 0 4px;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

h2,
h3,
p {
  margin-top: 0;
}

.muted,
.empty-state,
.source-meta,
.selected-file {
  color: #64748b;
}

.file-picker {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px dashed #94a3b8;
  border-radius: 8px;
  background: #f8fafc;
}

.upload-actions,
.section-heading,
.source-main,
.row-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.secondary-button {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 9px 12px;
  background: #fff;
  color: #172033;
  cursor: pointer;
}

.primary-button:disabled,
.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.error-alert {
  margin-bottom: 16px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fff1f2;
  color: #b91c1c;
  padding: 12px 14px;
}

.source-list {
  display: grid;
  gap: 12px;
}

.source-row {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
  background: #fff;
}

.source-row.active {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.status-badge,
.chunk-count {
  border-radius: 999px;
  padding: 5px 8px;
  background: #e2e8f0;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

.status-badge[data-status="ready"] {
  background: #dcfce7;
  color: #166534;
}

.status-badge[data-status="failed"] {
  background: #fee2e2;
  color: #991b1b;
}

.status-badge[data-status="processing"] {
  background: #dbeafe;
  color: #1d4ed8;
}

.source-error {
  color: #b91c1c;
}

.chunk-list {
  display: grid;
  gap: 12px;
}

.selected-source-name {
  color: #334155;
  font-weight: 700;
}

.chunk-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  background: #f8fafc;
}

.chunk-card p {
  white-space: pre-wrap;
}

@media (max-width: 900px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .upload-actions,
  .section-heading,
  .source-main,
  .row-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
```

- [ ] **Step 3: Run source-library tests**

Run from `apps/web`:

```powershell
npm run test -- source-library.spec.ts
```

Expected: PASS.

- [ ] **Step 4: Commit page implementation**

```powershell
git add apps/web/pages/spaces/[id]/index.vue apps/web/tests/source-library.spec.ts
git commit -m "feat: add source library upload page"
```

---

### Task 5: Add Upload and Ingestion Interaction Tests

**Files:**
- Modify: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Add file validation and API interaction tests**

Append these tests inside the existing `describe` block:

```ts
  it('blocks unsupported files before calling the API', async () => {
    const wrapper = mountPage()
    const file = new File(['pdf'], 'notes.pdf', { type: 'application/pdf' })
    const input = wrapper.find('input[type="file"]')

    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true
    })
    await input.trigger('change')
    await wrapper.find('button.primary-button').trigger('click')

    expect(wrapper.text()).toContain('This phase supports only .txt and .md files.')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('uploads markdown through presign, object PUT, uploaded confirmation, and list refresh', async () => {
    const wrapper = mountPage()
    await new Promise(resolve => setTimeout(resolve, 0))
    fetchMock.mockClear()
    fetchMock
      .mockResolvedValueOnce({
        source_id: '00000000-0000-0000-0000-000000000301',
        object_key: 'tenants/t/spaces/s/sources/source/intro.md',
        upload_url: 'http://storage.local/upload',
        method: 'PUT'
      })
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ source: { id: '00000000-0000-0000-0000-000000000301' } })
      .mockResolvedValueOnce({ sources: [] })

    const file = new File(['# Intro'], 'intro.md', { type: 'text/markdown' })
    const input = wrapper.find('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true
    })

    await input.trigger('change')
    await wrapper.find('button.primary-button').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/api/v1/uploads/presign',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-User-Id': '00000000-0000-0000-0000-000000000002',
          'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
        }),
        body: expect.objectContaining({
          study_space_id: '00000000-0000-0000-0000-000000000101',
          filename: 'intro.md',
          content_type: 'text/markdown'
        })
      })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://storage.local/upload',
      expect.objectContaining({
        method: 'PUT',
        headers: { 'Content-Type': 'text/markdown' },
        body: file
      })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8000/api/v1/sources/00000000-0000-0000-0000-000000000301/uploaded',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
        })
      })
    )
  })

  it('runs ingestion and then loads chunks for the selected source', async () => {
    fetchMock.mockResolvedValueOnce({
      sources: [
        {
          id: '00000000-0000-0000-0000-000000000201',
          tenant_id: '00000000-0000-0000-0000-000000000001',
          study_space_id: '00000000-0000-0000-0000-000000000101',
          filename: 'intro.md',
          content_type: 'text/markdown',
          object_key: 'tenants/t/spaces/s/sources/source/intro.md',
          status: 'uploaded',
          error_message: null,
          created_at: '2026-05-27T00:00:00Z'
        }
      ]
    })

    const wrapper = mountPage()
    await new Promise(resolve => setTimeout(resolve, 0))
    fetchMock.mockClear()
    fetchMock
      .mockResolvedValueOnce({
        job_id: '00000000-0000-0000-0000-000000000401',
        source_id: '00000000-0000-0000-0000-000000000201',
        status: 'completed',
        chunk_count: 1
      })
      .mockResolvedValueOnce({ sources: [] })
      .mockResolvedValueOnce({
        chunks: [
          {
            id: '00000000-0000-0000-0000-000000000501',
            source_id: '00000000-0000-0000-0000-000000000201',
            chunk_index: 0,
            text: 'Chunk text',
            citation: { page_number: 1 }
          }
        ]
      })

    await wrapper.findAll('button').find(button => button.text() === 'Run ingestion')?.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/api/v1/ingestion/sources/00000000-0000-0000-0000-000000000201/run',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8000/api/v1/sources/00000000-0000-0000-0000-000000000201/chunks',
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-User-Id': '00000000-0000-0000-0000-000000000002'
        })
      })
    )
    expect(wrapper.text()).toContain('Chunk text')
    expect(wrapper.text()).toContain('Page 1')
  })
```

- [ ] **Step 2: Run interaction tests**

Run from `apps/web`:

```powershell
npm run test -- source-library.spec.ts
```

Expected: PASS.

- [ ] **Step 3: Commit interaction tests**

```powershell
git add apps/web/tests/source-library.spec.ts
git commit -m "test: cover source upload and ingestion interactions"
```

---

### Task 6: Final Web Verification and Visual Check

**Files:**
- Read: `apps/web/pages/spaces/[id]/index.vue`
- Read: `apps/web/tests/source-library.spec.ts`

- [ ] **Step 1: Run full web tests**

Run from `apps/web`:

```powershell
npm run test
```

Expected: all Vitest tests PASS.

- [ ] **Step 2: Run typecheck**

Run from `apps/web`:

```powershell
npm run typecheck
```

Expected: PASS.

If typecheck fails because Nuxt generated files are missing, run:

```powershell
npm run build
```

Then fix any real TypeScript errors. Do not ignore TypeScript errors in the page.

- [ ] **Step 3: Start Nuxt dev server**

Run from `apps/web`:

```powershell
npm run dev -- --host 127.0.0.1 --port 3000
```

Expected: dev server starts at `http://127.0.0.1:3000`.

- [ ] **Step 4: Browser visual check**

Use the Browser plugin to open:

`http://127.0.0.1:3000/spaces/00000000-0000-0000-0000-000000000101`

Verify:

- Page is not blank.
- Two-column layout appears on desktop.
- Upload panel, source list, and chunk preview are visible.
- Text does not overlap.
- Buttons fit within their containers.
- Mobile viewport stacks the columns.

If the API server is not running, source-list loading may show an error. That is acceptable for visual layout verification as long as the static controls render.

- [ ] **Step 5: Commit visual polish if needed**

If browser verification requires CSS fixes, commit them:

```powershell
git add apps/web/pages/spaces/[id]/index.vue
git commit -m "fix: polish source library layout"
```

If no fixes are needed, do not create an empty commit.

## Final Verification

Before creating a PR, run from `apps/web`:

```powershell
npm run test
npm run typecheck
```

Record:

- Vitest result.
- Typecheck result.
- Browser visual check URL and outcome.

## Execution Order

1. Merge `codex/runtime-source-ingestion` into `main`.
2. Create `codex/source-library-upload-ux` worktree.
3. Execute Tasks 1-6 in order.
4. Push branch and open PR.
5. Preserve the worktree until PR feedback is resolved.

## Self-Review

- Spec coverage: This plan implements upload, source list, ingestion trigger, chunk preview, dev auth headers, invalid file rejection, and focused tests.
- Scope control: This plan only touches the study space detail page and its tests.
- Frontend-design alignment: The plan asks implementation workers to use a refined utilitarian workspace UI, stable responsive layout, scoped styles, visible states, and no hero or marketing composition.
- Type consistency: `SourceItem`, `UploadPresignResponse`, `SourceChunk`, and response object shapes match the backend API names from the runtime ingestion phase.
