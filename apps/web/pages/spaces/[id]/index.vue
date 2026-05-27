<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type SourceStatus = 'pending_upload' | 'uploaded' | 'processing' | 'ready' | 'failed' | string
type SourceFilter = 'all' | 'uploaded' | 'processing' | 'ready' | 'failed'
type UploadPhase = 'idle' | 'creating_url' | 'uploading_file' | 'confirming_upload' | 'refreshing_sources'

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
const activeFilter = ref<SourceFilter>('all')
const selectedFile = ref<File | null>(null)
const selectedSourceId = ref<string | null>(null)
const selectedSourceName = ref('')
const chunks = ref<SourceChunk[]>([])
const chunklessSourceIds = ref<Set<string>>(new Set())
const loadingSources = ref(false)
const uploadPhase = ref<UploadPhase>('idle')
const ingestingSourceId = ref<string | null>(null)
const loadingChunks = ref(false)
const errorMessage = ref('')

const uploading = computed(() => uploadPhase.value !== 'idle')
const canUpload = computed(() => selectedFile.value !== null && !uploading.value)
const selectedSource = computed(() => sources.value.find(source => source.id === selectedSourceId.value) ?? null)
const hasSelectedSource = computed(() => selectedSourceId.value !== null)
const sourceFilters = computed(() => [
  { key: 'all' as const, label: 'All', count: sources.value.length },
  { key: 'uploaded' as const, label: 'Uploaded', count: sources.value.filter(source => source.status === 'uploaded').length },
  {
    key: 'processing' as const,
    label: 'Processing',
    count: sources.value.filter(source => source.status === 'processing').length
  },
  { key: 'ready' as const, label: 'Ready', count: sources.value.filter(source => source.status === 'ready').length },
  { key: 'failed' as const, label: 'Failed', count: sources.value.filter(source => source.status === 'failed').length }
])
const filteredSources = computed(() => {
  if (activeFilter.value === 'all') return sources.value
  return sources.value.filter(source => source.status === activeFilter.value)
})
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

function ingestionActionLabel(source: SourceItem) {
  if (source.status === 'failed') return 'Retry ingestion'
  if (source.status === 'ready') return 'Re-run ingestion'
  return 'Run ingestion'
}

function contentTypeForFile(file: File) {
  const allowedMimeTypes = new Set([
    '',
    'text/plain',
    'text/markdown',
    'text/x-markdown',
    'application/octet-stream'
  ])
  if (!allowedMimeTypes.has(file.type)) return null

  const lowerName = file.name.toLowerCase()
  if (lowerName.endsWith('.md')) return 'text/markdown'
  if (lowerName.endsWith('.txt')) return 'text/plain'
  return null
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  const kib = bytes / 1024
  if (kib < 1024) return `${kib.toFixed(1)} KB`
  return `${(kib / 1024).toFixed(1)} MB`
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

  uploadPhase.value = 'creating_url'
  errorMessage.value = ''
  let uploadErrorMessage = 'Failed to create upload URL.'
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

    uploadErrorMessage = 'Failed to upload file to object storage.'
    uploadPhase.value = 'uploading_file'
    await $fetch(presign.upload_url, {
      method: 'PUT',
      headers: {
        'Content-Type': contentType
      },
      body: selectedFile.value
    })

    uploadErrorMessage = 'Failed to confirm upload completion.'
    uploadPhase.value = 'confirming_upload'
    await $fetch(`${config.public.apiBaseUrl}/sources/${presign.source_id}/uploaded`, {
      method: 'POST',
      headers: protectedHeaders()
    })

    selectedFile.value = null
    uploadPhase.value = 'refreshing_sources'
    await loadSources()
  } catch (error) {
    errorMessage.value = appendBackendMessage(uploadErrorMessage, error)
  } finally {
    uploadPhase.value = 'idle'
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

async function runSelectedSourceIngestion() {
  if (!selectedSource.value || !canRunIngestion(selectedSource.value)) return
  await runIngestion(selectedSource.value)
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

<template>
  <section class="space-detail page-enter">
    <div class="space-layout">
      <div class="space-main">
        <div class="topbar page-heading">
          <div>
            <p class="eyebrow">Study space</p>
            <h1>Study Space</h1>
            <p>Space ID: {{ spaceId }}</p>
          </div>
        </div>

        <section class="card route-overview">
          <div>
            <p class="eyebrow">Next action</p>
            <h2>Learning route foundation</h2>
            <p>Route generation will connect chapters, source chunks, and tutor sessions in the next product phase.</p>
          </div>
        </section>

        <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>

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
              <span>{{ filter.label }} {{ filter.count }}</span>
            </button>
          </div>

          <p v-if="loadingSources" class="muted">Loading sources...</p>
          <p v-else-if="sources.length === 0" class="empty-state">No sources yet. Upload a Markdown or text file to start.</p>
          <p v-else-if="filteredSources.length === 0" class="empty-state">No sources match this filter.</p>

          <div v-else class="source-list">
            <article
              v-for="source in filteredSources"
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
                  {{ ingestingSourceId === source.id ? 'Running...' : ingestionActionLabel(source) }}
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

      <aside class="space-rail">
        <section class="panel mentor-panel">
          <p class="eyebrow">AI Mentor</p>
          <h2>Ready for sources</h2>
          <p>Upload text or Markdown material, run ingestion, then inspect chunks before route generation.</p>
        </section>

        <section class="card chunk-preview">
          <div class="section-heading">
            <div>
              <p class="eyebrow">RAG preview</p>
              <h2>Chunk preview</h2>
            </div>
            <span v-if="chunks.length" class="chunk-count">{{ chunks.length }} chunks</span>
          </div>

          <p v-if="loadingChunks" class="muted">Loading chunks...</p>
          <div v-else-if="!hasSelectedSource" class="empty-state">Select a source to preview parsed chunks.</div>
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
          <div v-else class="chunk-list">
            <p class="selected-source-name">{{ selectedSourceName || selectedSource?.filename }}</p>
            <article v-for="chunk in chunks" :key="chunk.id" class="chunk-card">
              <h3>Chunk #{{ chunk.chunk_index }}</h3>
              <p>{{ chunk.text }}</p>
              <small>{{ citationSummary(chunk.citation) }}</small>
            </article>
          </div>
        </section>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.space-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.9fr);
  gap: 18px;
  align-items: start;
}

.space-main,
.space-rail {
  display: grid;
  gap: 18px;
}

.page-heading {
  min-height: 0;
}

.source-upload-card,
.source-list-card,
.chunk-preview {
  display: grid;
  gap: 16px;
}

.route-overview p,
.page-heading p,
.space-rail p {
  color: var(--color-muted);
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
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
  color: var(--color-muted);
}

.file-picker {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px dashed var(--color-border-strong);
  border-radius: 8px;
  background: var(--color-surface-muted);
}

.file-picker span {
  color: var(--color-text);
  font-weight: 700;
}

.selected-file-panel {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
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
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 700;
}

.file-meta dd {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
}

.upload-phase {
  color: var(--color-primary);
  font-weight: 700;
  margin: 10px 0 0;
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

.primary-button,
.secondary-button {
  min-height: 40px;
  white-space: nowrap;
}

.primary-button:disabled,
.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-button {
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 6px 10px;
}

.filter-button.active {
  border-color: var(--color-primary-bright);
  color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.14);
}

.source-list {
  display: grid;
  gap: 12px;
}

.source-row {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px;
  background: var(--color-surface);
  min-width: 0;
}

.source-row.active {
  border-color: var(--color-primary-bright);
  color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.14);
}

.chunk-count {
  border-radius: 999px;
  padding: 5px 8px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
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
  color: var(--color-error);
  overflow-wrap: anywhere;
}

.source-main,
.source-main > div,
.source-row h3,
.source-row p {
  min-width: 0;
  overflow-wrap: anywhere;
}

.chunk-list {
  display: grid;
  gap: 12px;
}

.selected-source-name {
  color: var(--color-text);
  font-weight: 700;
}

.chunk-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 12px;
  background: var(--color-surface-muted);
}

.chunk-card p {
  white-space: pre-wrap;
}

.preview-empty {
  display: grid;
  gap: 12px;
  justify-items: start;
}

@media (max-width: 1120px) {
  .space-layout {
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
