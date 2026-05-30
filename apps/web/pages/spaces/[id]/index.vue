<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

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

interface SourceUploadedResponse {
  source: SourceItem
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

interface PlannerActionExecutionResponse {
  action: PlannerAction
  session: {
    id: string
    chapter_id: string
  }
}

interface PlannerActionRouteDraftResponse {
  action: PlannerAction
  route_draft: RouteWithChapters
}

interface AgentRunLearningSignal {
  kind: string
  [key: string]: unknown
}

interface AgentRunTimelineItem {
  id?: string
  agent_type: string
  graph_name?: string | null
  status: string
  summary: string
  node_trace: string[]
  learning_signals: AgentRunLearningSignal[]
  thread_id: string | null
  checkpoint_backend: string | null
  state_schema_version?: number | null
  created_at?: string | null
  completed_at?: string | null
  latency_ms?: number | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  total_tokens?: number | null
  error_message?: string | null
}

const DEV_AUTH_HEADERS = {
  'X-User-Id': '00000000-0000-0000-0000-000000000002',
  'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
}

const route = useRoute()
const config = useRuntimeConfig()
const { isZh, loadLocale } = useLocalI18n()
const spaceId = computed(() => String(route.params.id))
const copy = computed(() => isZh.value ? {
  studySpace: '学习空间',
  spaceId: '空间 ID',
  learningRoute: '学习路线',
  activeRoute: '已激活路线',
  draftRoute: '路线草稿',
  noRoute: '还没有学习路线。',
  routeEmpty: '从你的目标和已提取资料分块生成路线。',
  generating: '生成中...',
  regenerateDraft: '重新生成草稿',
  generateRoute: '生成路线',
  activating: '激活中...',
  activateRoute: '激活路线',
  loadingRoutes: '正在加载学习路线...',
  days: '天',
  study: '学习',
  routeEmptyLong: '还没有学习路线。上传或提取资料后生成路线。',
  planner: '空间规划器',
  nextBest: '下一步最佳动作',
  plannerBody: '读取路线进度、导师状态和测验掌握度，不会自动改变你的路线。',
  planning: '规划中...',
  refreshPlan: '刷新计划',
  runPlanner: '运行规划器',
  loadingPlanner: '正在加载规划状态...',
  recommendedNext: '推荐下一步',
  noNext: '暂无必须继续的具体章节。',
  updated: '更新于',
  riskChapters: '风险章节',
  noRisk: '未检测到风险章节。',
  mastery: '掌握度',
  reviews: '复习',
  noReview: '暂无复习动作排队。',
  routeProposals: '路线建议',
  noRouteProposal: '暂无路线调整建议。',
  runPlannerHint: '激活路线或提交测验后运行规划器。',
  actionQueue: '动作队列',
  plannerActions: '规划动作',
  actionsBody: '先确认规划建议，再让它影响学习流程。',
  creating: '创建中...',
  createActions: '创建动作',
  createRuntimeActions: '创建运行动作',
  loadingActions: '正在加载规划动作...',
  noActions: '没有排队的规划动作。',
  accept: '接受',
  startReview: '开始复习',
  generateDraft: '生成草稿',
  complete: '完成',
  dismiss: '忽略',
  runtime: 'Agent 运行',
  recentRuns: '最近运行',
  runtimeBody: '当前学习空间的 L1 Planner、L2 Mentor 和 L3 Tutor 执行轨迹。',
  refresh: '刷新',
  loadingRuntime: '正在加载 agent 运行...',
  noRuns: '还没有记录 agent 运行。',
  sourceLibrary: '资料库',
  uploadMaterial: '上传学习资料',
  uploadBody: '支持 .txt、.md 和粘贴笔记。PDF、OCR 和网页导入后续补充。',
  chooseFile: '选择资料文件',
  noFile: '未选择文件',
  type: '类型',
  size: '大小',
  pasteFilename: '粘贴文件名',
  format: '格式',
  plainText: '纯文本',
  pastePlaceholder: '在这里粘贴笔记、摘录或复制的 Markdown。',
  adding: '添加中...',
  addPasted: '添加粘贴资料',
  sources: '资料',
  studyMaterials: '学习资料',
  filters: '资料状态筛选',
  loadingSources: '正在加载资料...',
  noSources: '还没有资料。上传 Markdown 或文本文件开始。',
  noSourceMatch: '没有匹配该筛选的资料。',
  created: '创建于',
  running: '运行中...',
  viewChunks: '查看分块',
  aiMentor: 'AI 导师',
  readyForSources: '等待资料',
  readyBody: '上传文本或 Markdown 资料，运行提取，然后在生成路线前检查分块。',
  ragPreview: 'RAG 预览',
  chunkPreview: '分块预览',
  chunks: '个分块',
  loadingChunks: '正在加载分块...',
  selectSource: '选择一个资料来预览解析后的分块。',
  noChunks: '这个资料还没有分块。'
} : {
  studySpace: 'Study space',
  spaceId: 'Space ID',
  learningRoute: 'Learning route',
  activeRoute: 'Active route',
  draftRoute: 'Draft route',
  noRoute: 'No learning route yet.',
  routeEmpty: 'Generate a route from your goal and ingested source chunks.',
  generating: 'Generating...',
  regenerateDraft: 'Regenerate draft',
  generateRoute: 'Generate route',
  activating: 'Activating...',
  activateRoute: 'Activate route',
  loadingRoutes: 'Loading learning routes...',
  days: 'days',
  study: 'Study',
  routeEmptyLong: 'No learning route yet. Generate a route after uploading or ingesting sources.',
  planner: 'Space planner',
  nextBest: 'Next best action',
  plannerBody: 'Reads route progress, mentor state, and quiz mastery without changing your route automatically.',
  planning: 'Planning...',
  refreshPlan: 'Refresh plan',
  runPlanner: 'Run planner',
  loadingPlanner: 'Loading planner state...',
  recommendedNext: 'Recommended next',
  noNext: 'No specific next chapter is required.',
  updated: 'Updated',
  riskChapters: 'Risk chapters',
  noRisk: 'No risk chapters detected.',
  mastery: 'Mastery',
  reviews: 'Reviews',
  noReview: 'No review action is queued.',
  routeProposals: 'Route proposals',
  noRouteProposal: 'No route adjustment proposed.',
  runPlannerHint: 'Run the planner after activating a route or submitting a quiz.',
  actionQueue: 'Action queue',
  plannerActions: 'Planner actions',
  actionsBody: 'Confirm planner suggestions before they affect your study flow.',
  creating: 'Creating...',
  createActions: 'Create actions',
  createRuntimeActions: 'Create runtime actions',
  loadingActions: 'Loading planner actions...',
  noActions: 'No planner actions queued.',
  accept: 'Accept',
  startReview: 'Start review',
  generateDraft: 'Generate draft',
  complete: 'Complete',
  dismiss: 'Dismiss',
  runtime: 'Agent runtime',
  recentRuns: 'Recent agent runs',
  runtimeBody: 'Latest L1 Planner, L2 Mentor, and L3 Tutor execution traces for this study space.',
  refresh: 'Refresh',
  loadingRuntime: 'Loading agent runtime...',
  noRuns: 'No agent runs recorded yet.',
  sourceLibrary: 'Source library',
  uploadMaterial: 'Upload learning material',
  uploadBody: 'Supports .txt, .md, and pasted notes. PDF, OCR, and webpage import will be added later.',
  chooseFile: 'Choose source file',
  noFile: 'No file selected',
  type: 'Type',
  size: 'Size',
  pasteFilename: 'Paste filename',
  format: 'Format',
  plainText: 'Plain text',
  pastePlaceholder: 'Paste notes, excerpts, or copied Markdown here.',
  adding: 'Adding...',
  addPasted: 'Add pasted source',
  sources: 'Sources',
  studyMaterials: 'Study materials',
  filters: 'Source status filters',
  loadingSources: 'Loading sources...',
  noSources: 'No sources yet. Upload a Markdown or text file to start.',
  noSourceMatch: 'No sources match this filter.',
  created: 'Created',
  running: 'Running...',
  viewChunks: 'View chunks',
  aiMentor: 'AI Mentor',
  readyForSources: 'Ready for sources',
  readyBody: 'Upload text or Markdown material, run ingestion, then inspect chunks before route generation.',
  ragPreview: 'RAG preview',
  chunkPreview: 'Chunk preview',
  chunks: 'chunks',
  loadingChunks: 'Loading chunks...',
  selectSource: 'Select a source to preview parsed chunks.',
  noChunks: 'This source has no chunks yet.'
})

const sources = ref<SourceItem[]>([])
const activeFilter = ref<SourceFilter>('all')
const selectedFile = ref<File | null>(null)
const pastedSourceFilename = ref('pasted-notes.md')
const pastedSourceContentType = ref<'text/markdown' | 'text/plain'>('text/markdown')
const pastedSourceContent = ref('')
const selectedSourceId = ref<string | null>(null)
const selectedSourceName = ref('')
const chunks = ref<SourceChunk[]>([])
const highlightedChunkId = ref<string | null>(null)
const routes = ref<RouteWithChapters[]>([])
const plannerState = ref<SpacePlannerState | null>(null)
const plannerActions = ref<PlannerAction[]>([])
const agentRuns = ref<AgentRunTimelineItem[]>([])
const selectedAgentRunId = ref<string | null>(null)
const chunklessSourceIds = ref<Set<string>>(new Set())
const loadingSources = ref(false)
const loadingRoutes = ref(false)
const loadingPlannerState = ref(false)
const loadingPlannerActions = ref(false)
const loadingAgentRuns = ref(false)
const generatingRoute = ref(false)
const runningPlanner = ref(false)
const creatingPlannerActions = ref(false)
const creatingRuntimeActions = ref(false)
const runtimeActionsMessage = ref('')
const activatingRouteId = ref<string | null>(null)
const updatingPlannerActionId = ref<string | null>(null)
const uploadPhase = ref<UploadPhase>('idle')
const creatingTextSource = ref(false)
const ingestingSourceId = ref<string | null>(null)
const loadingChunks = ref(false)
const errorMessage = ref('')

const uploading = computed(() => uploadPhase.value !== 'idle')
const canUpload = computed(() => selectedFile.value !== null && !uploading.value)
const canCreatePastedSource = computed(() => {
  return pastedSourceFilename.value.trim().length > 0 && pastedSourceContent.value.trim().length > 0 && !creatingTextSource.value
})
const selectedSource = computed(() => sources.value.find(source => source.id === selectedSourceId.value) ?? null)
const hasSelectedSource = computed(() => selectedSourceId.value !== null)
const activeRoute = computed(() => routes.value.find(item => item.route.status === 'active') ?? null)
const latestDraftRoute = computed(() => routes.value.find(item => item.route.status === 'draft') ?? null)
const visibleRoute = computed(() => latestDraftRoute.value ?? activeRoute.value ?? null)
const plannerNextChapter = computed(() => {
  if (!plannerState.value?.next_chapter_id || !visibleRoute.value) return null
  return visibleRoute.value.chapters.find(chapter => chapter.id === plannerState.value?.next_chapter_id) ?? null
})
const plannerUpdatedAt = computed(() => {
  if (!plannerState.value?.updated_at) return ''
  return new Date(plannerState.value.updated_at).toLocaleString()
})
const supervisionRefreshCount = computed(() => {
  return (plannerState.value?.evidence ?? []).filter(item => item.needs_supervision_refresh === true).length
})
const sourceFilters = computed(() => [
  { key: 'all' as const, label: isZh.value ? '全部' : 'All', count: sources.value.length },
  { key: 'uploaded' as const, label: isZh.value ? '已上传' : 'Uploaded', count: sources.value.filter(source => source.status === 'uploaded').length },
  {
    key: 'processing' as const,
    label: isZh.value ? '处理中' : 'Processing',
    count: sources.value.filter(source => source.status === 'processing').length
  },
  { key: 'ready' as const, label: isZh.value ? '就绪' : 'Ready', count: sources.value.filter(source => source.status === 'ready').length },
  { key: 'failed' as const, label: isZh.value ? '失败' : 'Failed', count: sources.value.filter(source => source.status === 'failed').length }
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
    idle: isZh.value ? '上传资料' : 'Upload source',
    creating_url: isZh.value ? '正在创建上传 URL...' : 'Creating upload URL...',
    uploading_file: isZh.value ? '正在上传文件...' : 'Uploading file...',
    confirming_upload: isZh.value ? '正在确认上传...' : 'Confirming upload...',
    refreshing_sources: isZh.value ? '正在刷新资料...' : 'Refreshing sources...'
  }
  return labels[uploadPhase.value]
})
const selectedAgentRun = computed(() => {
  if (!selectedAgentRunId.value) return null
  return agentRuns.value.find(run => runtimeRunKey(run) === selectedAgentRunId.value) ?? null
})

function protectedHeaders() {
  return DEV_AUTH_HEADERS
}

function formatStatus(status: SourceStatus) {
  const labels: Record<string, string> = {
    pending_upload: 'Pending upload',
    uploaded: isZh.value ? '已上传' : 'Uploaded',
    processing: isZh.value ? '处理中' : 'Processing',
    ready: isZh.value ? '就绪' : 'Ready',
    failed: isZh.value ? '失败' : 'Failed'
  }
  return labels[status] ?? status
}

function canRunIngestion(source: SourceItem) {
  return ['uploaded', 'ready', 'failed'].includes(source.status)
}

function ingestionActionLabel(source: SourceItem) {
  if (source.status === 'failed') return isZh.value ? '重试提取' : 'Retry ingestion'
  if (source.status === 'ready') return isZh.value ? '重新提取' : 'Re-run ingestion'
  return isZh.value ? '运行提取' : 'Run ingestion'
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

function queryStringValue(value: unknown) {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return typeof value[0] === 'string' ? value[0] : null
  return null
}

function sourceJumpSourceId() {
  return queryStringValue(route.query?.source_id)
}

function sourceJumpChunkId() {
  return queryStringValue(route.query?.chunk_id)
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
      checkpoint_backend: run.checkpoint_backend ?? null,
      graph_name: run.graph_name ?? null,
      state_schema_version: run.state_schema_version ?? null,
      created_at: run.created_at ?? null,
      completed_at: run.completed_at ?? null,
      latency_ms: run.latency_ms ?? null,
      prompt_tokens: run.prompt_tokens ?? null,
      completion_tokens: run.completion_tokens ?? null,
      total_tokens: run.total_tokens ?? null,
      error_message: run.error_message ?? null
    }))
}

function runtimeRunKey(run: AgentRunTimelineItem) {
  return run.id ?? `${run.agent_type}-${run.thread_id ?? 'no-thread'}`
}

function toggleAgentRun(run: AgentRunTimelineItem) {
  const runKey = runtimeRunKey(run)
  selectedAgentRunId.value = selectedAgentRunId.value === runKey ? null : runKey
}

function formatRuntimeMetric(value: number | string | null | undefined, suffix = '') {
  if (value === null || value === undefined || value === '') return 'Not recorded'
  return `${value}${suffix}`
}

function formatRuntimeDate(value: string | null | undefined) {
  if (!value) return 'Not recorded'
  const runtimeDate = new Date(value)
  if (Number.isNaN(runtimeDate.getTime())) return 'Not recorded'
  return runtimeDate.toLocaleString()
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

async function createRuntimeActions() {
  creatingRuntimeActions.value = true
  runtimeActionsMessage.value = ''
  errorMessage.value = ''
  try {
    const response = await $fetch<{ actions: PlannerAction[] }>(
      `${config.public.apiBaseUrl}/planner-actions/from-runtime-signals`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { study_space_id: spaceId.value }
      }
    )
    const actions = response.actions ?? []
    plannerActions.value = [
      ...actions,
      ...plannerActions.value.filter(existingAction => !actions.some(action => action.id === existingAction.id))
    ]
    runtimeActionsMessage.value =
      actions.length > 0 ? `Created ${actions.length} runtime actions.` : 'No new runtime actions found.'
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to create runtime actions.', error)
  } finally {
    creatingRuntimeActions.value = false
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

async function startReviewAction(action: PlannerAction) {
  if (!action.chapter_id || action.action_type !== 'review_chapter') return

  updatingPlannerActionId.value = action.id
  errorMessage.value = ''
  try {
    const response = await $fetch<PlannerActionExecutionResponse>(
      `${config.public.apiBaseUrl}/planner-actions/${action.id}/start-review`,
      {
        method: 'POST',
        headers: protectedHeaders()
      }
    )
    plannerActions.value = plannerActions.value.map(item => (item.id === action.id ? response.action : item))
    await navigateTo(`/chapters/${response.session.chapter_id}?session_id=${response.session.id}`)
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to start review.', error)
  } finally {
    updatingPlannerActionId.value = null
  }
}

async function generateRouteDraftFromAction(action: PlannerAction) {
  if (action.action_type !== 'route_adjustment') return

  updatingPlannerActionId.value = action.id
  errorMessage.value = ''
  try {
    const response = await $fetch<PlannerActionRouteDraftResponse>(
      `${config.public.apiBaseUrl}/planner-actions/${action.id}/route-draft`,
      {
        method: 'POST',
        headers: protectedHeaders()
      }
    )
    plannerActions.value = plannerActions.value.map(item => (item.id === action.id ? response.action : item))
    routes.value = [
      response.route_draft,
      ...routes.value.filter(item => item.route.id !== response.route_draft.route.id)
    ]
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to generate route draft from action.', error)
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

async function createPastedSource() {
  if (!canCreatePastedSource.value) return

  creatingTextSource.value = true
  errorMessage.value = ''
  try {
    const response = await $fetch<SourceUploadedResponse>(`${config.public.apiBaseUrl}/sources/from-text`, {
      method: 'POST',
      headers: protectedHeaders(),
      body: {
        study_space_id: spaceId.value,
        filename: pastedSourceFilename.value.trim(),
        content_type: pastedSourceContentType.value,
        content: pastedSourceContent.value
      }
    })
    pastedSourceContent.value = ''
    selectedSourceId.value = response.source.id
    selectedSourceName.value = response.source.filename
    await loadSources()
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to add pasted source.', error)
  } finally {
    creatingTextSource.value = false
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

async function loadChunks(source: SourceItem, highlightChunkId: string | null = null) {
  selectedSourceId.value = source.id
  selectedSourceName.value = source.filename
  highlightedChunkId.value = highlightChunkId
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
    if (highlightChunkId && response.chunks.some(chunk => chunk.id === highlightChunkId)) {
      void nextTick(() => {
        const element = document.getElementById(`source-chunk-${highlightChunkId}`)
        if (typeof element?.scrollIntoView !== 'function') return
        element.scrollIntoView({
          block: 'center',
          behavior: 'smooth'
        })
      })
    }
  } catch (error) {
    chunks.value = []
    errorMessage.value = appendBackendMessage('Failed to load chunks.', error)
  } finally {
    loadingChunks.value = false
  }
}

async function applySourceJump() {
  const sourceId = sourceJumpSourceId()
  if (!sourceId) return
  const linkedSource = sources.value.find(source => source.id === sourceId)
  if (!linkedSource) return
  await loadChunks(linkedSource, sourceJumpChunkId())
}

async function initializePage() {
  await loadSources()
  await applySourceJump()
  loadRoutes()
  loadAgentRuns()
}

onMounted(async () => {
  await loadLocale()
  void initializePage()
})
</script>

<template>
  <section class="space-detail page-enter">
    <div class="space-layout">
      <div class="space-main">
        <div class="topbar page-heading">
          <div>
            <p class="eyebrow">{{ copy.studySpace }}</p>
            <h1>{{ copy.studySpace }}</h1>
            <p>{{ copy.spaceId }}: {{ spaceId }}</p>
          </div>
        </div>

        <section class="card route-overview">
          <div class="section-heading">
            <div>
              <p class="eyebrow">{{ copy.learningRoute }}</p>
              <h2>{{ visibleRoute?.route.status === 'active' ? copy.activeRoute : visibleRoute ? copy.draftRoute : copy.noRoute }}</h2>
              <h3 v-if="visibleRoute" class="route-title">{{ visibleRoute.route.title }}</h3>
              <p v-if="visibleRoute">{{ visibleRoute.route.summary }}</p>
              <p v-else>{{ copy.routeEmpty }}</p>
            </div>
            <div class="route-actions">
              <button
                data-testid="generate-route"
                type="button"
                class="secondary-button"
                :disabled="generatingRoute"
                @click="generateRouteDraft"
              >
                {{ generatingRoute ? copy.generating : visibleRoute ? copy.regenerateDraft : copy.generateRoute }}
              </button>
              <button
                v-if="latestDraftRoute"
                data-testid="activate-route"
                type="button"
                class="primary-button"
                :disabled="activatingRouteId === latestDraftRoute.route.id"
                @click="activateRoute(latestDraftRoute.route.id)"
              >
                {{ activatingRouteId === latestDraftRoute.route.id ? copy.activating : copy.activateRoute }}
              </button>
            </div>
          </div>

          <p v-if="loadingRoutes" class="muted">{{ copy.loadingRoutes }}</p>
          <div v-else-if="visibleRoute" class="chapter-list">
            <article v-for="chapter in visibleRoute.chapters" :key="chapter.id" class="chapter-row">
              <span class="status-badge">{{ chapter.status }}</span>
              <div>
                <h3>{{ chapter.order_index }}. {{ chapter.title }}</h3>
                <p>{{ chapter.goal }}</p>
                <small>{{ chapter.estimated_days }} {{ copy.days }}</small>
              </div>
              <NuxtLink
                data-testid="study-chapter"
                class="secondary-button chapter-study-link"
                :to="`/chapters/${chapter.id}`"
              >
                {{ copy.study }}
              </NuxtLink>
            </article>
          </div>
          <p v-else class="empty-state">{{ copy.routeEmptyLong }}</p>
        </section>

        <section class="card planner-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">{{ copy.planner }}</p>
              <h2>{{ copy.nextBest }}</h2>
              <p class="muted">{{ copy.plannerBody }}</p>
            </div>
            <button
              data-testid="run-space-planner"
              type="button"
              class="secondary-button"
              :disabled="runningPlanner"
              @click="runSpacePlanner"
            >
              {{ runningPlanner ? copy.planning : plannerState ? copy.refreshPlan : copy.runPlanner }}
            </button>
          </div>

          <p v-if="loadingPlannerState" class="muted">{{ copy.loadingPlanner }}</p>
          <div v-else-if="plannerState" class="planner-grid">
            <article class="planner-summary">
              <span class="status-badge">Planner</span>
              <h3>{{ plannerState.summary }}</h3>
              <p v-if="plannerNextChapter">{{ copy.recommendedNext }}: {{ plannerNextChapter.order_index }}. {{ plannerNextChapter.title }}</p>
              <p v-else class="muted">{{ copy.noNext }}</p>
              <p v-if="supervisionRefreshCount" class="supervision-refresh-note">
                {{ supervisionRefreshCount }} {{ supervisionRefreshCount === 1 ? 'chapter needs' : 'chapters need' }} supervision refresh
              </p>
              <small v-if="plannerUpdatedAt">{{ copy.updated }} {{ plannerUpdatedAt }}</small>
            </article>

            <article class="planner-list">
              <h3>{{ copy.riskChapters }}</h3>
              <p v-if="plannerState.risk_chapters.length === 0" class="empty-state">{{ copy.noRisk }}</p>
              <ul v-else>
                <li v-for="risk in plannerState.risk_chapters" :key="risk.chapter_id">
                  <strong>{{ risk.title }}</strong>
                  <span>{{ risk.reason }}</span>
                  <small v-if="risk.score_percent !== null">{{ copy.mastery }} {{ risk.score_percent }}%</small>
                </li>
              </ul>
            </article>

            <article class="planner-list">
              <h3>{{ copy.reviews }}</h3>
              <p v-if="plannerState.review_recommendations.length === 0" class="empty-state">{{ copy.noReview }}</p>
              <ul v-else>
                <li v-for="review in plannerState.review_recommendations" :key="`${review.chapter_id}-${review.action}`">
                  <strong>{{ review.action }}</strong>
                  <span>{{ review.title }}: {{ review.reason }}</span>
                </li>
              </ul>
            </article>

            <article class="planner-list">
              <h3>{{ copy.routeProposals }}</h3>
              <p v-if="plannerState.route_adjustments.length === 0" class="empty-state">{{ copy.noRouteProposal }}</p>
              <ul v-else>
                <li v-for="proposal in plannerState.route_adjustments" :key="`${proposal.kind}-${proposal.title}`">
                  <strong>{{ proposal.title }}</strong>
                  <span>{{ proposal.rationale }}</span>
                </li>
              </ul>
            </article>
          </div>
          <p v-else class="empty-state">{{ copy.runPlannerHint }}</p>
        </section>

        <section class="card planner-actions-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">{{ copy.actionQueue }}</p>
              <h2>{{ copy.plannerActions }}</h2>
              <p class="muted">{{ copy.actionsBody }}</p>
            </div>
            <div class="row-actions planner-action-controls">
              <button
                data-testid="create-planner-actions"
                type="button"
                class="secondary-button"
                :disabled="creatingPlannerActions"
                @click="createPlannerActions"
              >
                {{ creatingPlannerActions ? copy.creating : copy.createActions }}
              </button>
              <button
                data-testid="create-runtime-actions"
                type="button"
                class="secondary-button"
                :disabled="creatingRuntimeActions"
                @click="createRuntimeActions"
              >
                {{ creatingRuntimeActions ? copy.creating : copy.createRuntimeActions }}
              </button>
            </div>
          </div>
          <p v-if="runtimeActionsMessage" class="muted">{{ runtimeActionsMessage }}</p>

          <p v-if="loadingPlannerActions" class="muted">{{ copy.loadingActions }}</p>
          <p v-else-if="plannerActions.length === 0" class="empty-state">{{ copy.noActions }}</p>
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
                  {{ copy.accept }}
                </button>
                <button
                  v-if="action.action_type === 'review_chapter' && action.chapter_id && action.status !== 'completed' && action.status !== 'dismissed'"
                  data-testid="start-review-action"
                  type="button"
                  class="primary-button"
                  :disabled="updatingPlannerActionId === action.id"
                  @click="startReviewAction(action)"
                >
                  {{ copy.startReview }}
                </button>
                <button
                  v-if="action.action_type === 'route_adjustment' && action.status !== 'completed' && action.status !== 'dismissed'"
                  data-testid="generate-route-draft-action"
                  type="button"
                  class="primary-button"
                  :disabled="updatingPlannerActionId === action.id"
                  @click="generateRouteDraftFromAction(action)"
                >
                  {{ copy.generateDraft }}
                </button>
                <button
                  v-if="action.status !== 'completed'"
                  type="button"
                  class="secondary-button"
                  :disabled="updatingPlannerActionId === action.id"
                  @click="updatePlannerAction(action, 'completed')"
                >
                  {{ copy.complete }}
                </button>
                <button
                  v-if="action.status === 'proposed'"
                  type="button"
                  class="secondary-button"
                  :disabled="updatingPlannerActionId === action.id"
                  @click="updatePlannerAction(action, 'dismissed')"
                >
                  {{ copy.dismiss }}
                </button>
              </div>
            </article>
          </div>
        </section>

        <section class="card agent-runtime-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">{{ copy.runtime }}</p>
              <h2>{{ copy.recentRuns }}</h2>
              <p class="muted">{{ copy.runtimeBody }}</p>
            </div>
            <button
              data-testid="refresh-agent-runs"
              type="button"
              class="secondary-button"
              :disabled="loadingAgentRuns"
              @click="loadAgentRuns"
            >
              {{ copy.refresh }}
            </button>
          </div>

          <p v-if="loadingAgentRuns" class="muted">{{ copy.loadingRuntime }}</p>
          <p v-else-if="agentRuns.length === 0" class="empty-state">{{ copy.noRuns }}</p>
          <div v-else class="agent-runtime-list">
            <article v-for="run in agentRuns" :key="run.id ?? `${run.agent_type}-${run.thread_id}`" class="agent-runtime-row">
              <button
                data-testid="agent-runtime-row-button"
                type="button"
                class="agent-runtime-header"
                :aria-expanded="selectedAgentRunId === runtimeRunKey(run)"
                @click="toggleAgentRun(run)"
              >
                <span class="agent-runtime-meta">
                  <span class="status-badge">{{ agentTypeLabel(run.agent_type) }}</span>
                  <span class="runtime-status">{{ run.status }}</span>
                </span>
                <span class="agent-runtime-body">
                  <span class="runtime-summary">{{ run.summary }}</span>
                  <span v-if="run.node_trace.length" class="runtime-trace">{{ run.node_trace.join(' -> ') }}</span>
                  <span v-else class="runtime-trace">No node trace recorded.</span>
                  <span v-if="run.learning_signals.length" class="signal-list" aria-label="Learning signals">
                    <span v-for="signal in run.learning_signals" :key="signal.kind" class="signal-chip">{{ signal.kind }}</span>
                  </span>
                  <span v-else class="muted">No learning signals.</span>
                </span>
              </button>
              <div
                v-if="selectedAgentRun && selectedAgentRunId === runtimeRunKey(run)"
                class="agent-runtime-detail"
              >
                <dl class="runtime-detail-grid">
                  <div>
                    <dt>Thread</dt>
                    <dd>{{ run.thread_id || 'Not recorded' }}</dd>
                  </div>
                  <div>
                    <dt>Graph</dt>
                    <dd>{{ run.graph_name || run.agent_type }}</dd>
                  </div>
                  <div>
                    <dt>Checkpoint</dt>
                    <dd>{{ run.checkpoint_backend || 'Not recorded' }}</dd>
                  </div>
                  <div>
                    <dt>Schema</dt>
                    <dd>{{ formatRuntimeMetric(run.state_schema_version) }}</dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>{{ formatRuntimeDate(run.created_at) }}</dd>
                  </div>
                  <div>
                    <dt>Completed</dt>
                    <dd>{{ formatRuntimeDate(run.completed_at) }}</dd>
                  </div>
                  <div>
                    <dt>Latency</dt>
                    <dd>{{ formatRuntimeMetric(run.latency_ms, ' ms') }}</dd>
                  </div>
                  <div>
                    <dt>Tokens</dt>
                    <dd>
                      {{ formatRuntimeMetric(run.total_tokens) }}
                      <span v-if="run.prompt_tokens != null || run.completion_tokens != null" class="runtime-token-breakdown">
                        ({{ formatRuntimeMetric(run.prompt_tokens, ' prompt') }},
                        {{ formatRuntimeMetric(run.completion_tokens, ' completion') }})
                      </span>
                    </dd>
                  </div>
                </dl>

                <div class="runtime-detail-section">
                  <h4>Node trace</h4>
                  <ol v-if="run.node_trace.length" class="runtime-node-list">
                    <li v-for="node in run.node_trace" :key="node">{{ node }}</li>
                  </ol>
                  <p v-else class="muted">No node trace recorded.</p>
                </div>

                <div class="runtime-detail-section">
                  <h4>Learning signals</h4>
                  <div v-if="run.learning_signals.length" class="signal-list" aria-label="Learning signals detail">
                    <span v-for="signal in run.learning_signals" :key="`detail-${signal.kind}`" class="signal-chip">
                      {{ signal.kind }}
                    </span>
                  </div>
                  <p v-else class="muted">No learning signals.</p>
                </div>

                <p v-if="run.error_message" class="runtime-error">{{ run.error_message }}</p>
              </div>
            </article>
          </div>
        </section>

        <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>

        <section class="card source-upload-card">
          <div>
            <p class="eyebrow">{{ copy.sourceLibrary }}</p>
            <h2>{{ copy.uploadMaterial }}</h2>
            <p class="muted">{{ copy.uploadBody }}</p>
          </div>

          <div class="source-input-grid">
            <div class="source-input-panel">
              <label class="file-picker">
                <span>{{ copy.chooseFile }}</span>
                <input type="file" accept=".txt,.md,text/plain,text/markdown" @change="onFileSelected">
              </label>

              <div class="selected-file-panel">
                <p class="selected-file">{{ selectedFile?.name || copy.noFile }}</p>
                <dl v-if="selectedFile" class="file-meta">
                  <div>
                    <dt>{{ copy.type }}</dt>
                    <dd>{{ inferredContentType }}</dd>
                  </div>
                  <div>
                    <dt>{{ copy.size }}</dt>
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
            </div>

            <div class="source-input-panel pasted-source-panel">
              <div class="inline-fields">
                <label>
                  <span>{{ copy.pasteFilename }}</span>
                  <input
                    v-model="pastedSourceFilename"
                    data-testid="pasted-source-filename"
                    type="text"
                    maxlength="255"
                    placeholder="pasted-notes.md"
                  >
                </label>
                <label>
                  <span>{{ copy.format }}</span>
                  <select v-model="pastedSourceContentType" data-testid="pasted-source-type">
                    <option value="text/markdown">Markdown</option>
                    <option value="text/plain">{{ copy.plainText }}</option>
                  </select>
                </label>
              </div>
              <textarea
                v-model="pastedSourceContent"
                data-testid="pasted-source-content"
                rows="7"
                :placeholder="copy.pastePlaceholder"
              />
              <button
                data-testid="add-pasted-source"
                class="secondary-button"
                type="button"
                :disabled="!canCreatePastedSource"
                @click="createPastedSource"
              >
                {{ creatingTextSource ? copy.adding : copy.addPasted }}
              </button>
            </div>
          </div>
        </section>

        <section class="card source-list-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">{{ copy.sources }}</p>
              <h2>{{ copy.studyMaterials }}</h2>
            </div>
            <button type="button" class="secondary-button" :disabled="loadingSources" @click="loadSources">
              {{ copy.refresh }}
            </button>
          </div>

          <div class="filter-bar" :aria-label="copy.filters">
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

          <p v-if="loadingSources" class="muted">{{ copy.loadingSources }}</p>
          <p v-else-if="sources.length === 0" class="empty-state">{{ copy.noSources }}</p>
          <p v-else-if="filteredSources.length === 0" class="empty-state">{{ copy.noSourceMatch }}</p>

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
              <p v-if="source.created_at" class="source-meta">{{ copy.created }} {{ new Date(source.created_at).toLocaleString() }}</p>

              <div class="row-actions">
                <button
                  v-if="canRunIngestion(source)"
                  type="button"
                  class="secondary-button"
                  :disabled="ingestingSourceId === source.id"
                  @click="runIngestion(source)"
                >
                  {{ ingestingSourceId === source.id ? copy.running : ingestionActionLabel(source) }}
                </button>
                <button
                  type="button"
                  class="secondary-button"
                  :disabled="chunklessSourceIds.has(source.id)"
                  @click="loadChunks(source)"
                >
                  {{ copy.viewChunks }}
                </button>
              </div>
            </article>
          </div>
        </section>
      </div>

      <aside class="space-rail">
        <section class="panel mentor-panel">
          <p class="eyebrow">{{ copy.aiMentor }}</p>
          <h2>{{ copy.readyForSources }}</h2>
          <p>{{ copy.readyBody }}</p>
        </section>

        <section class="card chunk-preview">
          <div class="section-heading">
            <div>
              <p class="eyebrow">{{ copy.ragPreview }}</p>
              <h2>{{ copy.chunkPreview }}</h2>
            </div>
            <span v-if="chunks.length" class="chunk-count">{{ chunks.length }} {{ copy.chunks }}</span>
          </div>

          <p v-if="loadingChunks" class="muted">{{ copy.loadingChunks }}</p>
          <div v-else-if="!hasSelectedSource" class="empty-state">{{ copy.selectSource }}</div>
          <div v-else-if="chunks.length === 0" class="empty-state preview-empty">
            <p>{{ copy.noChunks }}</p>
            <button
              v-if="selectedSource && canRunIngestion(selectedSource)"
              data-testid="preview-run-ingestion"
              type="button"
              class="secondary-button"
              :disabled="ingestingSourceId === selectedSource.id"
              @click="runSelectedSourceIngestion"
            >
              {{ ingestingSourceId === selectedSource.id ? copy.running : ingestionActionLabel(selectedSource) }}
            </button>
          </div>
          <div v-else class="chunk-list">
            <p class="selected-source-name">{{ selectedSourceName || selectedSource?.filename }}</p>
            <article
              v-for="chunk in chunks"
              :id="`source-chunk-${chunk.id}`"
              :key="chunk.id"
              class="chunk-card"
              :class="{ highlighted: highlightedChunkId === chunk.id }"
              :data-testid="`source-chunk-${chunk.id}`"
            >
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

.supervision-refresh-note {
  width: fit-content;
  border: 1px solid rgba(20, 184, 166, 0.32);
  border-radius: 999px;
  background: rgba(240, 253, 250, 0.9);
  color: #115e59;
  box-shadow: 0 12px 30px rgba(15, 118, 110, 0.08);
  font-size: 13px;
  font-weight: 800;
  line-height: 1.4;
  margin: 0;
  padding: 6px 10px;
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
  border: 1px solid rgba(20, 184, 166, 0.28);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: 0 10px 28px rgba(15, 118, 110, 0.08);
  min-width: 0;
  overflow: hidden;
}

.agent-runtime-header {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  display: grid;
  grid-template-columns: minmax(128px, 0.28fr) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  padding: 13px;
  text-align: left;
  width: 100%;
}

.agent-runtime-header:hover,
.agent-runtime-header:focus-visible {
  background: rgba(240, 253, 250, 0.8);
}

.agent-runtime-header:focus-visible {
  outline: 2px solid var(--color-primary-bright);
  outline-offset: -2px;
}

.agent-runtime-meta,
.agent-runtime-body {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.runtime-summary {
  font-size: 16px;
  font-weight: 800;
  line-height: 1.35;
}

.runtime-summary,
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
  display: block;
  border-left: 3px solid var(--color-primary-bright);
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  padding-left: 10px;
}

.agent-runtime-detail {
  display: grid;
  gap: 14px;
  border-top: 1px solid rgba(20, 184, 166, 0.2);
  background: #ffffff;
  padding: 14px;
}

.runtime-detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.runtime-detail-grid div {
  min-width: 0;
}

.runtime-detail-grid dt {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 800;
}

.runtime-detail-grid dd {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
}

.runtime-token-breakdown {
  color: var(--color-muted);
  font-size: 12px;
}

.runtime-detail-section {
  display: grid;
  gap: 8px;
}

.runtime-detail-section h4 {
  font-size: 13px;
  margin: 0;
}

.runtime-node-list {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 20px;
}

.runtime-node-list li {
  color: var(--color-muted);
  overflow-wrap: anywhere;
}

.runtime-error {
  border: 1px solid rgba(220, 38, 38, 0.24);
  border-radius: 8px;
  background: #fef2f2;
  color: var(--color-error);
  margin: 0;
  padding: 10px;
  overflow-wrap: anywhere;
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

.source-input-grid {
  display: grid;
  grid-template-columns: minmax(220px, 0.85fr) minmax(280px, 1.15fr);
  gap: 14px;
  align-items: stretch;
}

.source-input-panel {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.pasted-source-panel {
  border: 1px solid rgba(20, 184, 166, 0.26);
  border-radius: 8px;
  background:
    linear-gradient(145deg, rgba(240, 253, 250, 0.8), rgba(255, 255, 255, 0.96)),
    var(--color-surface);
  padding: 12px;
  box-shadow: 0 14px 32px rgba(15, 118, 110, 0.08);
}

.inline-fields {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(120px, 0.38fr);
  gap: 10px;
}

.inline-fields label,
.pasted-source-panel {
  min-width: 0;
}

.inline-fields span {
  display: block;
  margin-bottom: 6px;
  color: var(--color-text);
  font-size: 12px;
  font-weight: 700;
}

.inline-fields input,
.inline-fields select,
.pasted-source-panel textarea {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-text);
  font: inherit;
  outline: none;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}

.inline-fields input,
.inline-fields select {
  min-height: 40px;
  padding: 0 10px;
}

.pasted-source-panel textarea {
  min-height: 142px;
  resize: vertical;
  padding: 10px;
  line-height: 1.5;
}

.inline-fields input:focus,
.inline-fields select:focus,
.pasted-source-panel textarea:focus {
  border-color: rgba(20, 184, 166, 0.72);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.12);
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

  .source-input-grid,
  .inline-fields {
    grid-template-columns: 1fr;
  }

  .planner-action-row {
    grid-template-columns: 1fr;
  }

  .agent-runtime-header,
  .runtime-detail-grid {
    grid-template-columns: 1fr;
  }
}

/* Taste pass: internal tools page uses dividers and strips, not nested elevated cards. */
.space-layout {
  gap: 0;
  border-top: 1px solid rgba(161, 211, 202, 0.5);
}

.space-main {
  padding-right: 18px;
}

.space-rail {
  border-left: 1px solid rgba(161, 211, 202, 0.58);
  padding-left: 18px;
}

.route-overview,
.planner-panel,
.planner-actions-panel,
.agent-runtime-panel,
.source-upload-card,
.source-list-card,
.chunk-preview {
  border: 0;
  border-bottom: 1px solid rgba(161, 211, 202, 0.5);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 18px 0;
}

.route-overview {
  padding-top: 0;
}

.planner-summary,
.planner-list,
.planner-action-row,
.agent-runtime-row,
.selected-file-panel,
.pasted-source-panel,
.source-row,
.chunk-card {
  border-radius: 0;
  box-shadow: none;
}

.planner-summary,
.planner-list {
  border: 0;
  border-top: 1px solid rgba(161, 211, 202, 0.45);
  background: rgba(248, 253, 251, 0.56);
}

.chapter-row,
.planner-action-row,
.agent-runtime-row,
.source-row {
  border: 0;
  border-left: 3px solid transparent;
  border-bottom: 1px solid rgba(161, 211, 202, 0.42);
  background: transparent;
}

.chapter-row:hover,
.source-row.active {
  border-left-color: #14b8a6;
  background: rgba(255, 255, 255, 0.58);
  box-shadow: none;
}

.pasted-source-panel,
.selected-file-panel {
  background: rgba(255, 255, 255, 0.62);
}

.chunk-card {
  border: 0;
  border-left: 2px solid rgba(20, 184, 166, 0.42);
  background: rgba(236, 253, 245, 0.52);
}

.chunk-card.highlighted {
  border-left-color: #0f766e;
  background: rgba(204, 251, 241, 0.78);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.14);
}

@media (max-width: 1120px) {
  .space-main {
    padding-right: 0;
  }

  .space-rail {
    border-left: 0;
    padding-left: 0;
  }
}
</style>
