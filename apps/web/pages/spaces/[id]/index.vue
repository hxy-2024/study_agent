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
const hasSelectedSource = computed(() => selectedSourceId.value !== null)

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
    await $fetch(presign.upload_url, {
      method: 'PUT',
      headers: {
        'Content-Type': contentType
      },
      body: selectedFile.value
    })

    uploadErrorMessage = 'Failed to confirm upload completion.'
    await $fetch(`${config.public.apiBaseUrl}/sources/${presign.source_id}/uploaded`, {
      method: 'POST',
      headers: protectedHeaders()
    })

    selectedFile.value = null
    await loadSources()
  } catch (error) {
    errorMessage.value = appendBackendMessage(uploadErrorMessage, error)
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
        <div v-else-if="!hasSelectedSource" class="empty-state">Select a source to preview parsed chunks.</div>
        <div v-else-if="chunks.length === 0" class="empty-state">This source has no chunks yet. Run ingestion first.</div>
        <div v-else class="chunk-list">
          <p class="selected-source-name">{{ selectedSourceName || selectedSource?.filename }}</p>
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

.file-picker span {
  color: #334155;
  font-weight: 700;
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
