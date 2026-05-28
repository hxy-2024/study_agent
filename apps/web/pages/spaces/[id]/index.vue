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

interface LearningRoute {
  id: string
  study_space_id: string
  version: number
  status: 'draft' | 'active' | 'archived' | string
  title: string
  summary: string
  generation_strategy: string
  created_at: string | null
  activated_at: string | null
}

interface RouteChapter {
  id: string
  learning_route_id: string
  order_index: number
  title: string
  goal: string
  summary: string
  estimated_days: number
  status: string
  source_chunk_refs: Array<Record<string, unknown>>
}

interface RouteWithChapters {
  route: LearningRoute
  chapters: RouteChapter[]
}

interface RoutesListResponse {
  routes: RouteWithChapters[]
}

interface PlannerChapterRisk {
  chapter_id: string
  title: string
  reason: string
  score_percent: number | null
}

interface PlannerReviewRecommendation {
  chapter_id: string
  title: string
  action: string
  reason: string
}

interface PlannerRouteAdjustment {
  kind: string
  chapter_id: string | null
  title: string
  rationale: string
}

interface SpacePlannerState {
  id: string
  study_space_id: string
  summary: string
  next_chapter_id: string | null
  risk_chapters: PlannerChapterRisk[]
  review_recommendations: PlannerReviewRecommendation[]
  route_adjustments: PlannerRouteAdjustment[]
  evidence: Array<Record<string, unknown>>
  updated_at: string | null
}

interface PlannerAction {
  id: string
  study_space_id: string
  chapter_id: string | null
  source_planner_state_id: string | null
  action_type: string
  status: string
  title: string
  rationale: string
  payload: Record<string, unknown>
  created_at: string | null
  updated_at: string | null
}

interface AgentRunLearningSignal {
  kind: string
  [key: string]: unknown
}

interface AgentRunTimelineItem {
  id?: string
  agent_type: string
  status: string
  summary: string
  node_trace: string[]
  learning_signals: AgentRunLearningSignal[]
  thread_id: string | null
  checkpoint_backend: string | null
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
const routes = ref<RouteWithChapters[]>([])
const plannerState = ref<SpacePlannerState | null>(null)
const plannerActions = ref<PlannerAction[]>([])
const agentRuns = ref<AgentRunTimelineItem[]>([])
const chunklessSourceIds = ref<Set<string>>(new Set())
const loadingSources = ref(false)
const loadingRoutes = ref(false)
const loadingPlannerState = ref(false)
const loadingPlannerActions = ref(false)
const loadingAgentRuns = ref(false)
const generatingRoute = ref(false)
const runningPlanner = ref(false)
const creatingPlannerActions = ref(false)
const activatingRouteId = ref<string | null>(null)
const updatingPlannerActionId = ref<string | null>(null)
const uploadPhase = ref<UploadPhase>('idle')
const ingestingSourceId = ref<string | null>(null)
const loadingChunks = ref(false)
const errorMessage = ref('')

const uploading = computed(() => uploadPhase.value !== 'idle')
const canUpload = computed(() => selectedFile.value !== null && !uploading.value)
const selectedSource = computed(() => sources.value.find(source => source.id === selectedSourceId.value) ?? null)
const hasSelectedSource = computed(() => selectedSourceId.value !== null)
const activeRoute = computed(() => routes.value.find(item => item.route.status === 'active') ?? null)
const latestDraftRoute = computed(() => routes.value.find(item => item.route.status === 'draft') ?? null)
const visibleRoute = computed(() => activeRoute.value ?? latestDraftRoute.value ?? null)
const plannerNextChapter = computed(() => {
  if (!plannerState.value?.next_chapter_id || !visibleRoute.value) return null
  return visibleRoute.value.chapters.find(chapter => chapter.id === plannerState.value?.next_chapter_id) ?? null
})
const plannerUpdatedAt = computed(() => {
  if (!plannerState.value?.updated_at) return ''
  return new Date(plannerState.value.updated_at).toLocaleString()
})
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

function normalizePlannerState(response: SpacePlannerState): SpacePlannerState | null {
  if (!response?.id || !response.summary) return null
  return {
    ...response,
    risk_chapters: response.risk_chapters ?? [],
    review_recommendations: response.review_recommendations ?? [],
    route_adjustments: response.route_adjustments ?? [],
    evidence: response.evidence ?? []
  }
}

function normalizeAgentRuns(response: { runs?: AgentRunTimelineItem[] } | null | undefined): AgentRunTimelineItem[] {
  return (response?.runs ?? [])
    .filter(run => run?.agent_type && run.status)
    .map(run => ({
      ...run,
      summary: run.summary || 'No summary recorded.',
      node_trace: Array.isArray(run.node_trace) ? run.node_trace.filter(Boolean).map(String) : [],
      learning_signals: Array.isArray(run.learning_signals)
        ? run.learning_signals
            .map(signal => (typeof signal === 'string' ? { kind: signal } : signal))
            .filter((signal): signal is AgentRunLearningSignal => Boolean(signal?.kind))
        : [],
      thread_id: run.thread_id ?? null,
      checkpoint_backend: run.checkpoint_backend ?? null
    }))
}

function agentTypeLabel(agentType: string) {
  const labels: Record<string, string> = {
    space_planner: 'L1 Planner',
    chapter_mentor: 'L2 Mentor',
    session_tutor: 'L3 Tutor'
  }
  return labels[agentType] ?? agentType
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

async function loadRoutes() {
  loadingRoutes.value = true
  errorMessage.value = ''
  try {
    const response = await $fetch<RoutesListResponse>(
      `${config.public.apiBaseUrl}/study-spaces/${spaceId.value}/routes`,
      { headers: protectedHeaders() }
    )
    routes.value = response.routes ?? []
    if (routes.value.some(item => item.route.status === 'active')) {
      await loadPlannerState()
      await loadPlannerActions()
    } else {
      plannerState.value = null
      plannerActions.value = []
    }
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to load learning routes.', error)
  } finally {
    loadingRoutes.value = false
  }
}

async function loadPlannerState() {
  loadingPlannerState.value = true
  try {
    plannerState.value = await $fetch<SpacePlannerState>(
      `${config.public.apiBaseUrl}/study-spaces/${spaceId.value}/planner-state`,
      { headers: protectedHeaders() }
    )
    plannerState.value = normalizePlannerState(plannerState.value)
  } catch {
    plannerState.value = null
  } finally {
    loadingPlannerState.value = false
  }
}

async function loadPlannerActions() {
  loadingPlannerActions.value = true
  try {
    const response = await $fetch<{ actions: PlannerAction[] }>(
      `${config.public.apiBaseUrl}/study-spaces/${spaceId.value}/planner-actions`,
      { headers: protectedHeaders() }
    )
    plannerActions.value = response.actions ?? []
  } catch {
    plannerActions.value = []
  } finally {
    loadingPlannerActions.value = false
  }
}

async function loadAgentRuns() {
  loadingAgentRuns.value = true
  try {
    const response = await $fetch<{ runs: AgentRunTimelineItem[] }>(
      `${config.public.apiBaseUrl}/study-spaces/${spaceId.value}/agent-runs?limit=8`,
      { headers: protectedHeaders() }
    )
    agentRuns.value = normalizeAgentRuns(response)
  } catch {
    agentRuns.value = []
  } finally {
    loadingAgentRuns.value = false
  }
}

async function runSpacePlanner() {
  runningPlanner.value = true
  errorMessage.value = ''
  try {
    plannerState.value = await $fetch<SpacePlannerState>(
      `${config.public.apiBaseUrl}/agents/space-planner/run`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { study_space_id: spaceId.value }
      }
    )
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to run space planner.', error)
  } finally {
    runningPlanner.value = false
  }
}

async function createPlannerActions() {
  creatingPlannerActions.value = true
  errorMessage.value = ''
  try {
    const response = await $fetch<{ actions: PlannerAction[] }>(
      `${config.public.apiBaseUrl}/planner-actions/from-latest-state`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { study_space_id: spaceId.value }
      }
    )
    plannerActions.value = response.actions ?? []
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to create planner actions.', error)
  } finally {
    creatingPlannerActions.value = false
  }
}

async function updatePlannerAction(action: PlannerAction, status: string) {
  updatingPlannerActionId.value = action.id
  errorMessage.value = ''
  try {
    const response = await $fetch<PlannerAction>(
      `${config.public.apiBaseUrl}/planner-actions/${action.id}/status`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { status }
      }
    )
    plannerActions.value = plannerActions.value.map(item => (item.id === action.id ? response : item))
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to update planner action.', error)
  } finally {
    updatingPlannerActionId.value = null
  }
}

async function generateRouteDraft() {
  generatingRoute.value = true
  errorMessage.value = ''
  try {
    const response = await $fetch<RouteWithChapters>(
      `${config.public.apiBaseUrl}/study-spaces/${spaceId.value}/route-drafts`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { max_chapters: 5 }
      }
    )
    routes.value = [response, ...routes.value.filter(item => item.route.id !== response.route.id)]
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to generate learning route.', error)
  } finally {
    generatingRoute.value = false
  }
}

async function activateRoute(routeId: string) {
  activatingRouteId.value = routeId
  errorMessage.value = ''
  try {
    const response = await $fetch<RouteWithChapters>(
      `${config.public.apiBaseUrl}/routes/${routeId}/activate`,
      {
        method: 'POST',
        headers: protectedHeaders()
      }
    )
    routes.value = [
      response,
      ...routes.value
        .filter(item => item.route.id !== routeId)
        .map(item => ({
          ...item,
          route: item.route.status === 'active' ? { ...item.route, status: 'archived' } : item.route
        }))
    ]
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to activate learning route.', error)
  } finally {
    activatingRouteId.value = null
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
  loadRoutes()
  loadAgentRuns()
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
          <div class="section-heading">
            <div>
              <p class="eyebrow">Learning route</p>
              <h2>{{ visibleRoute?.route.status === 'active' ? 'Active route' : visibleRoute ? 'Draft route' : 'No learning route yet.' }}</h2>
              <h3 v-if="visibleRoute" class="route-title">{{ visibleRoute.route.title }}</h3>
              <p v-if="visibleRoute">{{ visibleRoute.route.summary }}</p>
              <p v-else>Generate a route from your goal and ingested source chunks.</p>
            </div>
            <div class="route-actions">
              <button
                data-testid="generate-route"
                type="button"
                class="secondary-button"
                :disabled="generatingRoute"
                @click="generateRouteDraft"
              >
                {{ generatingRoute ? 'Generating...' : visibleRoute ? 'Regenerate draft' : 'Generate route' }}
              </button>
              <button
                v-if="latestDraftRoute"
                data-testid="activate-route"
                type="button"
                class="primary-button"
                :disabled="activatingRouteId === latestDraftRoute.route.id"
                @click="activateRoute(latestDraftRoute.route.id)"
              >
                {{ activatingRouteId === latestDraftRoute.route.id ? 'Activating...' : 'Activate route' }}
              </button>
            </div>
          </div>

          <p v-if="loadingRoutes" class="muted">Loading learning routes...</p>
          <div v-else-if="visibleRoute" class="chapter-list">
            <article v-for="chapter in visibleRoute.chapters" :key="chapter.id" class="chapter-row">
              <span class="status-badge">{{ chapter.status }}</span>
              <div>
                <h3>{{ chapter.order_index }}. {{ chapter.title }}</h3>
                <p>{{ chapter.goal }}</p>
                <small>{{ chapter.estimated_days }} days</small>
              </div>
              <NuxtLink
                data-testid="study-chapter"
                class="secondary-button chapter-study-link"
                :to="`/chapters/${chapter.id}`"
              >
                Study
              </NuxtLink>
            </article>
          </div>
          <p v-else class="empty-state">No learning route yet. Generate a route after uploading or ingesting sources.</p>
        </section>

        <section class="card planner-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Space planner</p>
              <h2>Next best action</h2>
              <p class="muted">Reads route progress, mentor state, and quiz mastery without changing your route automatically.</p>
            </div>
            <button
              data-testid="run-space-planner"
              type="button"
              class="secondary-button"
              :disabled="runningPlanner"
              @click="runSpacePlanner"
            >
              {{ runningPlanner ? 'Planning...' : plannerState ? 'Refresh plan' : 'Run planner' }}
            </button>
          </div>

          <p v-if="loadingPlannerState" class="muted">Loading planner state...</p>
          <div v-else-if="plannerState" class="planner-grid">
            <article class="planner-summary">
              <span class="status-badge">Planner</span>
              <h3>{{ plannerState.summary }}</h3>
              <p v-if="plannerNextChapter">Recommended next: {{ plannerNextChapter.order_index }}. {{ plannerNextChapter.title }}</p>
              <p v-else class="muted">No specific next chapter is required.</p>
              <small v-if="plannerUpdatedAt">Updated {{ plannerUpdatedAt }}</small>
            </article>

            <article class="planner-list">
              <h3>Risk chapters</h3>
              <p v-if="plannerState.risk_chapters.length === 0" class="empty-state">No risk chapters detected.</p>
              <ul v-else>
                <li v-for="risk in plannerState.risk_chapters" :key="risk.chapter_id">
                  <strong>{{ risk.title }}</strong>
                  <span>{{ risk.reason }}</span>
                  <small v-if="risk.score_percent !== null">Mastery {{ risk.score_percent }}%</small>
                </li>
              </ul>
            </article>

            <article class="planner-list">
              <h3>Reviews</h3>
              <p v-if="plannerState.review_recommendations.length === 0" class="empty-state">No review action is queued.</p>
              <ul v-else>
                <li v-for="review in plannerState.review_recommendations" :key="`${review.chapter_id}-${review.action}`">
                  <strong>{{ review.action }}</strong>
                  <span>{{ review.title }}: {{ review.reason }}</span>
                </li>
              </ul>
            </article>

            <article class="planner-list">
              <h3>Route proposals</h3>
              <p v-if="plannerState.route_adjustments.length === 0" class="empty-state">No route adjustment proposed.</p>
              <ul v-else>
                <li v-for="proposal in plannerState.route_adjustments" :key="`${proposal.kind}-${proposal.title}`">
                  <strong>{{ proposal.title }}</strong>
                  <span>{{ proposal.rationale }}</span>
                </li>
              </ul>
            </article>
          </div>
          <p v-else class="empty-state">Run the planner after activating a route or submitting a quiz.</p>
        </section>

        <section class="card planner-actions-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Action queue</p>
              <h2>Planner actions</h2>
              <p class="muted">Confirm planner suggestions before they affect your study flow.</p>
            </div>
            <button
              data-testid="create-planner-actions"
              type="button"
              class="secondary-button"
              :disabled="creatingPlannerActions"
              @click="createPlannerActions"
            >
              {{ creatingPlannerActions ? 'Creating...' : 'Create actions' }}
            </button>
          </div>

          <p v-if="loadingPlannerActions" class="muted">Loading planner actions...</p>
          <p v-else-if="plannerActions.length === 0" class="empty-state">No planner actions queued.</p>
          <div v-else class="planner-action-list">
            <article v-for="action in plannerActions" :key="action.id" class="planner-action-row">
              <span class="status-badge">{{ action.status }}</span>
              <div>
                <h3>{{ action.title }}</h3>
                <p>{{ action.rationale }}</p>
              </div>
              <div class="row-actions">
                <button
                  v-if="action.status === 'proposed'"
                  data-testid="accept-planner-action"
                  type="button"
                  class="secondary-button"
                  :disabled="updatingPlannerActionId === action.id"
                  @click="updatePlannerAction(action, 'accepted')"
                >
                  Accept
                </button>
                <button
                  v-if="action.status !== 'completed'"
                  type="button"
                  class="secondary-button"
                  :disabled="updatingPlannerActionId === action.id"
                  @click="updatePlannerAction(action, 'completed')"
                >
                  Complete
                </button>
                <button
                  v-if="action.status === 'proposed'"
                  type="button"
                  class="secondary-button"
                  :disabled="updatingPlannerActionId === action.id"
                  @click="updatePlannerAction(action, 'dismissed')"
                >
                  Dismiss
                </button>
              </div>
            </article>
          </div>
        </section>

        <section class="card agent-runtime-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Agent runtime</p>
              <h2>Recent agent runs</h2>
              <p class="muted">Latest L1 Planner, L2 Mentor, and L3 Tutor execution traces for this study space.</p>
            </div>
            <button
              data-testid="refresh-agent-runs"
              type="button"
              class="secondary-button"
              :disabled="loadingAgentRuns"
              @click="loadAgentRuns"
            >
              Refresh
            </button>
          </div>

          <p v-if="loadingAgentRuns" class="muted">Loading agent runtime...</p>
          <p v-else-if="agentRuns.length === 0" class="empty-state">No agent runs recorded yet.</p>
          <div v-else class="agent-runtime-list">
            <article v-for="run in agentRuns" :key="run.id ?? `${run.agent_type}-${run.thread_id}`" class="agent-runtime-row">
              <div class="agent-runtime-meta">
                <span class="status-badge">{{ agentTypeLabel(run.agent_type) }}</span>
                <span class="runtime-status">{{ run.status }}</span>
              </div>
              <div class="agent-runtime-body">
                <h3>{{ run.summary }}</h3>
                <p v-if="run.node_trace.length" class="runtime-trace">{{ run.node_trace.join(' -> ') }}</p>
                <p v-else class="runtime-trace">No node trace recorded.</p>
                <div v-if="run.learning_signals.length" class="signal-list" aria-label="Learning signals">
                  <span v-for="signal in run.learning_signals" :key="signal.kind" class="signal-chip">{{ signal.kind }}</span>
                </div>
                <p v-else class="muted">No learning signals.</p>
              </div>
            </article>
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

.route-overview {
  display: grid;
  gap: 16px;
}

.planner-panel {
  display: grid;
  gap: 16px;
  border-color: rgba(20, 184, 166, 0.34);
  box-shadow: 0 18px 48px rgba(15, 118, 110, 0.12);
}

.agent-runtime-panel {
  display: grid;
  gap: 16px;
  border-color: rgba(20, 184, 166, 0.3);
  box-shadow: 0 16px 42px rgba(15, 118, 110, 0.1);
}

.planner-grid {
  display: grid;
  grid-template-columns: minmax(240px, 1.05fr) repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.planner-summary,
.planner-list {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(240, 253, 250, 0.72), var(--color-surface));
  padding: 14px;
  min-width: 0;
}

.planner-summary {
  display: grid;
  gap: 8px;
}

.planner-summary h3 {
  font-size: 17px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.planner-summary small,
.planner-list small {
  color: var(--color-primary);
  font-weight: 800;
}

.planner-list h3 {
  font-size: 15px;
  margin-bottom: 10px;
}

.planner-list ul {
  display: grid;
  gap: 10px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.planner-list li {
  display: grid;
  gap: 4px;
  border-top: 1px solid var(--color-border);
  padding-top: 10px;
}

.planner-list li:first-child {
  border-top: 0;
  padding-top: 0;
}

.planner-list strong,
.planner-list span {
  overflow-wrap: anywhere;
}

.planner-list span {
  color: var(--color-muted);
}

.planner-action-list {
  display: grid;
  gap: 12px;
}

.planner-action-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  padding: 12px;
}

.planner-action-row h3,
.planner-action-row p {
  overflow-wrap: anywhere;
}

.planner-action-row p {
  color: var(--color-muted);
}

.agent-runtime-list {
  display: grid;
  gap: 12px;
}

.agent-runtime-row {
  display: grid;
  grid-template-columns: minmax(128px, 0.28fr) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  border: 1px solid rgba(20, 184, 166, 0.28);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: 0 10px 28px rgba(15, 118, 110, 0.08);
  padding: 13px;
  min-width: 0;
}

.agent-runtime-meta,
.agent-runtime-body {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.agent-runtime-body h3 {
  font-size: 16px;
  line-height: 1.35;
}

.agent-runtime-body h3,
.runtime-trace {
  overflow-wrap: anywhere;
}

.runtime-status {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.runtime-trace {
  border-left: 3px solid var(--color-primary-bright);
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  padding-left: 10px;
}

.signal-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.signal-chip {
  border: 1px solid rgba(20, 184, 166, 0.28);
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
  max-width: 100%;
  overflow-wrap: anywhere;
  padding: 6px 8px;
}

.route-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.route-title {
  color: var(--color-text);
  font-size: 18px;
  line-height: 1.3;
  margin-bottom: 6px;
}

.chapter-list {
  display: grid;
  gap: 12px;
}

.chapter-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  padding: 12px;
}

.chapter-row h3,
.chapter-row p {
  overflow-wrap: anywhere;
}

.chapter-row p {
  color: var(--color-muted);
}

.chapter-row small {
  color: var(--color-primary);
  font-weight: 800;
}

.chapter-study-link {
  align-self: start;
  text-decoration: none;
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
  .route-actions,
  .section-heading,
  .source-main,
  .row-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .chapter-row {
    grid-template-columns: 1fr;
  }

  .planner-grid {
    grid-template-columns: 1fr;
  }

  .planner-action-row {
    grid-template-columns: 1fr;
  }

  .agent-runtime-row {
    grid-template-columns: 1fr;
  }
}
</style>
