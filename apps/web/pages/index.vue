<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

const store = useStudySpacesStore()
const config = useRuntimeConfig()

interface DashboardSpace {
  id: string
  name: string
  goal: string
  status: string
  target_days: number
  created_at?: string
}

interface DashboardAction {
  id: string
  title: string
  status: string
  study_space_id: string
  chapter_id?: string | null
}

interface DashboardAgentRun {
  id?: string
  agent_type: string
  status: string
  summary: string
}

interface DashboardRecommendationAction {
  title: string
  action_label: string
  action_url: string
  recommendation_type: string
  reason?: string | null
  estimated_minutes?: number | null
  study_space_id?: string | null
  chapter_id?: string | null
}

interface DashboardRecommendation extends DashboardRecommendationAction {
  agent_type: string
  freshness: string
  secondary_actions: DashboardRecommendationAction[]
}

type TodayRecommendationIntent = 'balanced' | 'new_material' | 'review' | 'quiz'

interface MainAgentMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  recommendation?: DashboardRecommendation
}

interface DashboardSummary {
  spaces: DashboardSpace[]
  pending_actions: DashboardAction[]
  supervision_refresh_count: number
  recent_agent_runs: DashboardAgentRun[]
  today_recommendation?: DashboardRecommendation | null
}

interface ChapterListResponse {
  chapters?: Array<{
    id: string
    status: string
    order_index: number
  }>
}

interface RoutesListResponse {
  routes?: Array<{
    chapters?: Array<{
      id: string
      status: string
      order_index: number
    }>
  }>
}

const dashboard = ref<DashboardSummary | null>(null)
const dashboardLoading = ref(false)
const spaceSearch = ref('')
const selectedSpaceId = ref('')
const continueChapterBySpace = ref<Record<string, string>>({})
const deletingSpaceId = ref('')
const archivedSpaces = ref<DashboardSpace[]>([])
const restoringSpaceId = ref('')

const fallbackSpaces = computed(() => store.spaces.filter(space => space.status !== 'archived'))
const activeSpaces = computed(() => dashboard.value?.spaces ?? fallbackSpaces.value)
const visibleSpaces = computed(() => {
  const query = spaceSearch.value.trim().toLowerCase()
  if (!query) return activeSpaces.value
  return activeSpaces.value.filter((space) => {
    return `${space.name} ${space.goal} ${space.status}`.toLowerCase().includes(query)
  })
})
const currentSpace = computed(() => {
  return visibleSpaces.value.find(space => space.id === selectedSpaceId.value) ?? visibleSpaces.value[0] ?? activeSpaces.value[0] ?? null
})
const pendingActionCount = computed(() => dashboard.value?.pending_actions?.length ?? 0)
const pendingActionLabel = computed(() => `${pendingActionCount.value} ${pendingActionCount.value === 1 ? 'pending action' : 'pending actions'}`)
const supervisionRefreshCount = computed(() => dashboard.value?.supervision_refresh_count ?? 0)
const supervisionRefreshLabel = computed(() => {
  return `${supervisionRefreshCount.value} ${supervisionRefreshCount.value === 1 ? 'supervision refresh' : 'supervision refreshes'}`
})
const recentAgentRuns = computed(() => dashboard.value?.recent_agent_runs ?? [])
function getContinueChapterId(spaceId: string) {
  const pendingChapterId = dashboard.value?.pending_actions.find(action => {
    return action.study_space_id === spaceId && Boolean(action.chapter_id)
  })?.chapter_id ?? null
  return pendingChapterId ?? continueChapterBySpace.value[spaceId] ?? null
}

const continueChapterId = computed(() => currentSpace.value ? getContinueChapterId(currentSpace.value.id) : null)
const continueHref = computed(() => continueChapterId.value ? `/chapters/${continueChapterId.value}` : '/spaces/new')
const continueLabel = computed(() => continueChapterId.value ? 'Continue study' : 'Prepare route')
const todayRecommendation = computed(() => dashboard.value?.today_recommendation ?? null)
const todayActionHref = computed(() => todayRecommendation.value?.action_url ?? continueHref.value)
const todayActionLabel = computed(() => todayRecommendation.value?.action_label ?? continueLabel.value)
const todayEstimatedMinutes = computed(() => todayRecommendation.value?.estimated_minutes ?? null)
const todayRecommendationAvailableMinutes = ref(30)
const todayRecommendationIntent = ref<TodayRecommendationIntent>('balanced')
const todayRecommendationLoading = ref(false)
const todayRecommendationError = ref('')
const mainAgentOpen = ref(false)
const mainAgentPrompt = ref('')
const mainAgentMessageId = ref(0)
const mainAgentMessages = ref<MainAgentMessage[]>([
  {
    id: mainAgentMessageId.value++,
    role: 'assistant',
    content: 'Tell me what kind of session you want. I can adjust today\'s plan around your time, energy, and study intent.'
  }
])
const currentExportUrl = computed(() => currentSpace.value ? `${config.public.apiBaseUrl}/study-spaces/${currentSpace.value.id}/export` : '')
const currentMarkdownExportUrl = computed(() => currentSpace.value ? `${config.public.apiBaseUrl}/study-spaces/${currentSpace.value.id}/export?format=markdown` : '')
const today = new Date()
const currentDay = today.getDate()
const calendarDays = Array.from({ length: 35 }, (_, index) => index + 1)
const progressPercent = computed(() => {
  if (!currentSpace.value) return 0
  return Math.max(12, Math.min(78, Math.round(100 / Math.max(1, currentSpace.value.target_days) * 7)))
})

function devAuthHeaders() {
  return {
    'X-User-Id': '00000000-0000-0000-0000-000000000002',
    'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
  }
}

function selectSpace(spaceId: string) {
  selectedSpaceId.value = spaceId
}

function ensureDashboardSummary() {
  if (dashboard.value) return dashboard.value
  return {
    spaces: [],
    pending_actions: [],
    supervision_refresh_count: 0,
    recent_agent_runs: [],
    today_recommendation: null
  }
}

function inferMainAgentRequest(prompt: string) {
  const normalized = prompt.toLowerCase()
  let availableMinutes = todayRecommendationAvailableMinutes.value
  const minuteMatch = normalized.match(/\b(15|30|45|60|90)\b/)
  if (minuteMatch) {
    availableMinutes = Number(minuteMatch[1])
  }

  let intent: TodayRecommendationIntent = todayRecommendationIntent.value
  if (/\bquiz|test|exam|测验|考试\b/.test(normalized)) {
    intent = 'quiz'
  } else if (/\breview|revise|weak|forgot|复习|薄弱|回顾\b/.test(normalized)) {
    intent = 'review'
  } else if (/\bnew|next|continue|新|继续|下一/.test(normalized)) {
    intent = 'new_material'
  } else if (/\bbalanced|mix|综合|均衡\b/.test(normalized)) {
    intent = 'balanced'
  }

  return {
    available_minutes: availableMinutes,
    intent
  }
}

async function requestTodayRecommendation(overrides?: {
  available_minutes?: number
  intent?: TodayRecommendationIntent
}) {
  if (todayRecommendationLoading.value) return

  if (typeof overrides?.available_minutes === 'number') {
    todayRecommendationAvailableMinutes.value = overrides.available_minutes
  }
  if (overrides?.intent) {
    todayRecommendationIntent.value = overrides.intent
  }

  todayRecommendationLoading.value = true
  todayRecommendationError.value = ''
  try {
    const recommendation = await $fetch<DashboardRecommendation>(`${config.public.apiBaseUrl}/dashboard/recommendation`, {
      method: 'POST',
      headers: devAuthHeaders(),
      body: {
        available_minutes: todayRecommendationAvailableMinutes.value,
        intent: todayRecommendationIntent.value
      }
    })
    dashboard.value = {
      ...ensureDashboardSummary(),
      today_recommendation: recommendation
    }
  } catch (error) {
    todayRecommendationError.value = error instanceof Error ? error.message : 'Request failed'
  } finally {
    todayRecommendationLoading.value = false
  }
}

function openMainAgent() {
  mainAgentOpen.value = true
}

function closeMainAgent() {
  mainAgentOpen.value = false
}

async function sendMainAgentPrompt(prompt?: string) {
  const content = (prompt ?? mainAgentPrompt.value).trim()
  if (!content || todayRecommendationLoading.value) return

  const request = inferMainAgentRequest(content)
  todayRecommendationAvailableMinutes.value = request.available_minutes
  todayRecommendationIntent.value = request.intent
  mainAgentPrompt.value = ''
  mainAgentMessages.value.push({
    id: mainAgentMessageId.value++,
    role: 'user',
    content
  })

  await requestTodayRecommendation(request)
  if (todayRecommendationError.value) {
    mainAgentMessages.value.push({
      id: mainAgentMessageId.value++,
      role: 'assistant',
      content: `Unable to load recommendation: ${todayRecommendationError.value}`
    })
    return
  }

  if (todayRecommendation.value) {
    mainAgentMessages.value.push({
      id: mainAgentMessageId.value++,
      role: 'assistant',
      content: todayRecommendation.value.reason ?? 'I updated today\'s plan based on your request.',
      recommendation: todayRecommendation.value
    })
  }
}

async function archiveSpace(spaceId: string, spaceName: string) {
  if (deletingSpaceId.value) return
  if (!window.confirm(`Delete "${spaceName}"? This will archive the space.`)) return

  deletingSpaceId.value = spaceId
  try {
    await $fetch(`${config.public.apiBaseUrl}/study-spaces/${spaceId}`, {
      method: 'DELETE',
      headers: devAuthHeaders()
    })
    await Promise.all([store.loadSpaces(), loadDashboard()])
    await loadArchivedSpaces()
  } finally {
    deletingSpaceId.value = ''
  }
}

async function loadArchivedSpaces() {
  try {
    archivedSpaces.value = await $fetch<DashboardSpace[]>(`${config.public.apiBaseUrl}/study-spaces/archived`, {
      headers: devAuthHeaders()
    })
  } catch {
    archivedSpaces.value = []
  }
}

async function restoreSpace(spaceId: string) {
  if (restoringSpaceId.value) return
  restoringSpaceId.value = spaceId
  try {
    await $fetch(`${config.public.apiBaseUrl}/study-spaces/${spaceId}/restore`, {
      method: 'POST',
      headers: devAuthHeaders()
    })
    await Promise.all([store.loadSpaces(), loadDashboard(), loadArchivedSpaces()])
  } finally {
    restoringSpaceId.value = ''
  }
}

async function loadDashboard() {
  dashboardLoading.value = true
  try {
    dashboard.value = await $fetch<DashboardSummary>(`${config.public.apiBaseUrl}/dashboard`)
  } catch {
    dashboard.value = null
  } finally {
    dashboardLoading.value = false
  }
}

async function loadContinueChapter(spaceId: string) {
  if (getContinueChapterId(spaceId)) return
  if (Object.prototype.hasOwnProperty.call(continueChapterBySpace.value, spaceId)) return

  let nextChapterId: string | null = null
  try {
    const response = await $fetch<ChapterListResponse>(`${config.public.apiBaseUrl}/study-spaces/${spaceId}/chapters`, {
      headers: devAuthHeaders()
    })
    const chapters = response.chapters ?? []
    const nextChapter = chapters.find(chapter => chapter.status !== 'completed') ?? chapters[0]
    nextChapterId = nextChapter?.id ?? null
  } catch {
    nextChapterId = null
  }

  if (!nextChapterId) {
    try {
      const routesResponse = await $fetch<RoutesListResponse>(`${config.public.apiBaseUrl}/study-spaces/${spaceId}/routes`, {
        headers: devAuthHeaders()
      })
      for (const route of routesResponse.routes ?? []) {
        const chapters = route.chapters ?? []
        const nextChapter = chapters.find(chapter => chapter.status !== 'completed') ?? chapters[0]
        if (nextChapter) {
          nextChapterId = nextChapter.id
          break
        }
      }
    } catch {
      nextChapterId = null
    }
  }

  continueChapterBySpace.value = {
    ...continueChapterBySpace.value,
    [spaceId]: nextChapterId ?? ''
  }
}

onMounted(() => {
  store.loadSpaces()
  loadDashboard()
  loadArchivedSpaces()
})

watch(
  () => currentSpace.value?.id,
  (spaceId) => {
    if (spaceId) loadContinueChapter(spaceId)
  },
  { immediate: true }
)
</script>

<template>
  <section class="dashboard page-enter">
    <div class="dashboard-grid">
      <aside class="spaces-column" aria-label="Study spaces">
        <div class="spaces-toolbar">
          <label class="space-search">
            <span class="sr-only">Search spaces</span>
            <input v-model="spaceSearch" class="input" type="search" placeholder="Search spaces">
          </label>
          <NuxtLink class="primary-button compact-button" to="/spaces/new">New</NuxtLink>
        </div>

        <section v-if="store.loading" class="card skeleton" aria-label="Loading study spaces" />

        <section v-else-if="!activeSpaces.length" class="empty-state dashboard-empty">
          <p class="eyebrow">Start here</p>
          <h2>Create your first study space</h2>
          <p>Set a goal, upload material, and let the workspace organize a route.</p>
          <NuxtLink class="primary-button" to="/spaces/new">New Study Space</NuxtLink>
        </section>

        <div v-else class="space-list">
          <article
            v-for="space in visibleSpaces"
            :key="space.id"
            class="space-row"
            :class="{ active: currentSpace?.id === space.id }"
          >
            <button class="space-row-main" type="button" @click="selectSpace(space.id)">
              <strong>{{ space.name }}</strong>
              <small>{{ space.goal }}</small>
            </button>
            <div class="space-row-actions">
              <NuxtLink
                v-if="getContinueChapterId(space.id)"
                class="space-row-continue"
                :to="`/chapters/${getContinueChapterId(space.id)}`"
              >
                Continue study
              </NuxtLink>
              <button
                class="space-row-delete"
                type="button"
                :disabled="deletingSpaceId === space.id"
                :aria-label="`Delete ${space.name}`"
                title="Delete space"
                @click="archiveSpace(space.id, space.name)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M4 7h16" />
                  <path d="M9 7V5h6v2" />
                  <path d="M8 7l1 12h6l1-12" />
                  <path d="M10 11v4" />
                  <path d="M14 11v4" />
                </svg>
              </button>
            </div>
          </article>
          <p v-if="!visibleSpaces.length" class="empty-state">No spaces match this search.</p>
        </div>
      </aside>

      <section class="dashboard-main">
        <div class="section-heading dashboard-heading">
          <div>
            <p class="eyebrow">Home</p>
            <h1>Learning dashboard</h1>
            <p>Pick a space, continue the current route, or review today's local agent activity.</p>
          </div>
        </div>

        <section v-if="currentSpace" class="card continue-panel">
          <div class="continue-copy">
            <p class="eyebrow">{{ todayRecommendation ? 'Main Agent' : 'Continue' }}</p>
            <h2>{{ todayRecommendation?.title ?? currentSpace.name }}</h2>
            <p>{{ todayRecommendation?.reason ?? currentSpace.goal }}</p>
            <div class="progress-track" aria-label="Current space progress">
              <span :style="{ width: `${progressPercent}%` }" />
            </div>
            <small v-if="todayEstimatedMinutes">{{ todayEstimatedMinutes }} min suggested · {{ todayRecommendation?.freshness }}</small>
            <small v-else>{{ progressPercent }}% route foundation prepared · {{ currentSpace.target_days }} target days</small>
            <div v-if="todayRecommendation?.secondary_actions?.length" class="today-secondary-list">
              <NuxtLink
                v-for="action in todayRecommendation.secondary_actions"
                :key="`${action.recommendation_type}-${action.action_url}-${action.title}`"
                class="today-secondary-action"
                :to="action.action_url"
              >
                <strong>{{ action.title }}</strong>
                <span>{{ action.action_label }}</span>
              </NuxtLink>
            </div>
          </div>
          <div class="continue-actions">
            <span class="status-badge">{{ currentSpace.status }}</span>
            <NuxtLink class="primary-button" :to="todayActionHref">{{ todayActionLabel }}</NuxtLink>
          </div>
        </section>

        <section v-if="currentSpace" class="panel export-panel">
          <div>
            <p class="eyebrow">Data safety</p>
            <h2>Export current space</h2>
            <p>Download a local snapshot before large edits or cleanup.</p>
          </div>
          <div class="export-actions">
            <a class="secondary-button" :href="currentExportUrl" target="_blank" rel="noreferrer">JSON</a>
            <a class="secondary-button" :href="currentMarkdownExportUrl" target="_blank" rel="noreferrer">Markdown</a>
          </div>
        </section>

        <section v-else class="card continue-panel dashboard-empty">
          <div>
            <p class="eyebrow">No active space</p>
            <h2>Your dashboard is ready</h2>
            <p>Create a study space to start the local learning loop.</p>
          </div>
          <NuxtLink class="primary-button" to="/spaces/new">New Study Space</NuxtLink>
        </section>

        <div class="dashboard-stats">
          <section class="panel">
            <p class="eyebrow">Today</p>
            <h2>Study queue</h2>
            <p v-if="dashboardLoading">Loading local dashboard...</p>
            <p v-else>{{ pendingActionLabel }}</p>
            <p>{{ supervisionRefreshLabel }}</p>
          </section>

          <section class="panel mentor-panel">
            <p class="eyebrow">AI Mentor</p>
            <h2>{{ recentAgentRuns.length ? 'Recent runtime' : 'Ready for sources' }}</h2>
            <p v-if="recentAgentRuns.length">{{ recentAgentRuns[0]?.summary }}</p>
            <p v-else>Upload text or Markdown in a study space to prepare retrieval and route generation.</p>
          </section>
        </div>

        <section v-if="archivedSpaces.length" class="panel archived-panel">
          <div class="section-heading archived-heading">
            <div>
              <p class="eyebrow">Archived</p>
              <h2>Archived spaces</h2>
            </div>
          </div>
          <div class="archived-list">
            <article v-for="space in archivedSpaces" :key="space.id" class="archived-row">
              <div>
                <strong>{{ space.name }}</strong>
                <small>{{ space.goal }}</small>
              </div>
              <button
                class="secondary-button"
                type="button"
                :disabled="restoringSpaceId === space.id"
                :data-testid="`restore-space-${space.id}`"
                @click="restoreSpace(space.id)"
              >
                Restore
              </button>
            </article>
          </div>
        </section>
      </section>

      <aside class="calendar-column" aria-label="Calendar and events">
        <section class="calendar-panel">
          <div class="calendar-heading">
            <div>
              <p class="eyebrow">Calendar</p>
              <h2>Today</h2>
            </div>
            <strong>{{ currentDay }}</strong>
          </div>
          <div class="calendar-grid" aria-label="Local calendar">
            <span v-for="day in calendarDays" :key="day" :class="{ today: day === currentDay }">{{ day }}</span>
          </div>
          <div class="event-list">
            <button type="button">Add diary</button>
            <button type="button">Add event</button>
          </div>
        </section>
      </aside>
    </div>

    <button
      type="button"
      class="main-agent-fab"
      data-testid="main-agent-fab"
      aria-label="Open Main Agent"
      @click="openMainAgent"
    >
      <span class="main-agent-fab-orbit" aria-hidden="true" />
      <span class="main-agent-fab-core">AI</span>
    </button>

    <section
      v-if="mainAgentOpen"
      class="main-agent-window"
      aria-label="Main Agent conversation"
    >
      <header class="main-agent-header">
        <div>
          <p class="eyebrow">Main Agent</p>
          <h2>Plan today's study</h2>
        </div>
        <button type="button" class="main-agent-close" aria-label="Close Main Agent" @click="closeMainAgent">
          ×
        </button>
      </header>

      <div class="main-agent-scope">
        Reads learning state, updates dashboard recommendations, and opens approved study actions.
      </div>

      <div class="main-agent-messages">
        <article
          v-for="message in mainAgentMessages"
          :key="message.id"
          class="main-agent-message"
          :class="message.role"
        >
          <p>{{ message.content }}</p>
          <NuxtLink
            v-if="message.recommendation"
            class="main-agent-message-action"
            :to="message.recommendation.action_url"
          >
            {{ message.recommendation.action_label }}
          </NuxtLink>
        </article>
        <article v-if="todayRecommendationLoading" class="main-agent-message assistant">
          <p>Thinking through today's best next step...</p>
        </article>
      </div>

      <div class="main-agent-prompts" aria-label="Suggested prompts">
        <button type="button" @click="sendMainAgentPrompt('I only have 15 minutes and want to review')">15 min review</button>
        <button type="button" @click="sendMainAgentPrompt('I want new material for the next hour')">New material</button>
        <button type="button" @click="sendMainAgentPrompt('Quiz me today')">Quiz me</button>
      </div>

      <form class="main-agent-form" data-testid="main-agent-form" @submit.prevent="sendMainAgentPrompt()">
        <input
          v-model="mainAgentPrompt"
          data-testid="main-agent-input"
          type="text"
          placeholder="Tell Main Agent what you need today..."
          :disabled="todayRecommendationLoading"
        >
        <button type="submit" :disabled="todayRecommendationLoading || !mainAgentPrompt.trim()">Send</button>
      </form>
    </section>
  </section>
</template>

<style scoped>
.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr) minmax(250px, 290px);
  gap: 16px;
  align-items: start;
}

.dashboard-main,
.spaces-column,
.calendar-column,
.dashboard-stats {
  display: grid;
  gap: 14px;
}

.dashboard-heading {
  min-height: auto;
  margin-bottom: 0;
}

.section-heading p,
.continue-panel p,
.dashboard-empty p,
.panel p {
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

.continue-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.continue-copy {
  min-width: 0;
}

.progress-track {
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-primary-soft);
  margin: 18px 0 8px;
}

.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-bright));
  animation: progress-in 520ms ease both;
}

.continue-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.today-secondary-list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.today-secondary-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid rgba(161, 211, 202, 0.48);
  color: var(--color-text);
  padding-top: 8px;
  text-decoration: none;
}

.today-secondary-action strong,
.today-secondary-action span {
  font-size: 13px;
}

.today-secondary-action span {
  color: var(--color-primary);
  font-weight: 800;
}

.main-agent-fab {
  position: fixed;
  right: 26px;
  bottom: 24px;
  z-index: 40;
  width: 66px;
  height: 66px;
  border: 1px solid rgba(20, 184, 166, 0.5);
  border-radius: 999px;
  background: radial-gradient(circle at 35% 30%, #ccfbf1, #14b8a6 56%, #0f766e);
  box-shadow: 0 18px 38px rgba(15, 118, 110, 0.28);
  color: white;
  cursor: pointer;
  display: grid;
  place-items: center;
}

.main-agent-fab-orbit {
  position: absolute;
  inset: -7px;
  border: 1px solid rgba(20, 184, 166, 0.38);
  border-radius: inherit;
  animation: agent-pulse 2.8s ease-in-out infinite;
}

.main-agent-fab-core {
  position: relative;
  font-size: 18px;
  font-weight: 900;
}

.main-agent-window {
  position: fixed;
  right: 26px;
  bottom: 104px;
  z-index: 41;
  width: min(430px, calc(100vw - 32px));
  max-height: min(680px, calc(100dvh - 132px));
  border: 1px solid rgba(161, 211, 202, 0.72);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(240, 253, 250, 0.94), rgba(255, 255, 255, 0.94)),
    var(--color-surface);
  box-shadow: 0 24px 70px rgba(15, 118, 110, 0.22);
  display: grid;
  grid-template-rows: auto auto minmax(180px, 1fr) auto auto;
  overflow: hidden;
}

.main-agent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 18px 12px;
}

.main-agent-header h2 {
  margin: 0;
}

.main-agent-close {
  width: 34px;
  height: 34px;
  border: 1px solid rgba(161, 211, 202, 0.7);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--color-text);
  cursor: pointer;
  font-size: 22px;
  line-height: 1;
}

.main-agent-scope {
  margin: 0 18px 12px;
  border-left: 3px solid var(--color-primary-bright);
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.45;
  padding-left: 10px;
}

.main-agent-messages {
  display: grid;
  gap: 10px;
  overflow: auto;
  padding: 0 18px 14px;
}

.main-agent-message {
  max-width: 86%;
  border-radius: 14px;
  padding: 10px 12px;
}

.main-agent-message p {
  margin: 0;
}

.main-agent-message.assistant {
  justify-self: start;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(161, 211, 202, 0.48);
}

.main-agent-message.user {
  justify-self: end;
  background: #0f766e;
  color: white;
}

.main-agent-message-action {
  display: inline-flex;
  margin-top: 10px;
  color: var(--color-primary);
  font-weight: 900;
  text-decoration: none;
}

.main-agent-prompts {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 0 18px 12px;
}

.main-agent-prompts button,
.main-agent-form button {
  border: 1px solid rgba(20, 184, 166, 0.42);
  border-radius: 10px;
  background: rgba(204, 251, 241, 0.62);
  color: var(--color-primary);
  cursor: pointer;
  font-weight: 850;
  min-height: 36px;
  padding: 0 12px;
  white-space: nowrap;
}

.main-agent-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  border-top: 1px solid rgba(161, 211, 202, 0.5);
  padding: 12px;
}

.main-agent-form input {
  min-width: 0;
  border: 1px solid rgba(161, 211, 202, 0.72);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.86);
  color: var(--color-text);
  min-height: 40px;
  padding: 0 12px;
}

.main-agent-form button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.spaces-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.compact-button {
  min-height: 42px;
  padding-inline: 13px;
}

.space-list {
  display: grid;
  gap: 8px;
  max-height: calc(100vh - 150px);
  overflow: auto;
  padding-right: 2px;
}

.space-row {
  position: relative;
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.88);
  color: var(--color-text);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  padding: 12px 48px 12px 12px;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.space-row:hover,
.space-row.active {
  border-color: var(--color-primary-bright);
  box-shadow: 0 10px 26px rgba(15, 118, 110, 0.1);
  transform: translateY(-1px);
}

.space-row strong,
.space-row small {
  display: block;
  overflow-wrap: anywhere;
}

.space-row-main {
  appearance: none;
  background: transparent;
  border: 0;
  color: inherit;
  cursor: pointer;
  display: block;
  width: 100%;
  padding: 0;
  text-align: left;
}

.space-row small {
  color: var(--color-muted);
  margin-top: 4px;
}

.space-row-actions {
  align-items: end;
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: flex-end;
}

.space-row-continue {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}

.space-row-continue:hover {
  text-decoration: underline;
}

.space-row-delete {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 30px;
  height: 30px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  color: var(--color-error);
  cursor: pointer;
  display: inline-grid;
  place-items: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 160ms ease, border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
}

.space-row-delete svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.space-row:hover .space-row-delete,
.space-row:focus-within .space-row-delete {
  opacity: 1;
  pointer-events: auto;
}

.space-row-delete:hover {
  border-color: rgba(220, 38, 38, 0.25);
  background: #fff5f5;
  box-shadow: 0 8px 20px rgba(220, 38, 38, 0.12);
  transform: translateY(-1px);
}

@media (hover: none) {
  .space-row-delete {
    opacity: 1;
    pointer-events: auto;
  }
}

.mentor-panel {
  border-color: var(--color-border-strong);
}

.calendar-panel {
  aspect-ratio: 1;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background:
    radial-gradient(circle at top right, rgba(20, 184, 166, 0.16), transparent 34%),
    rgba(255, 255, 255, 0.94);
  box-shadow: var(--shadow-card);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 12px;
  padding: 15px;
}

.calendar-heading {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
}

.calendar-heading h2 {
  margin-bottom: 0;
}

.calendar-heading strong {
  color: var(--color-primary);
  font-size: 36px;
  line-height: 1;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
}

.calendar-grid span {
  border-radius: 6px;
  color: var(--color-muted);
  display: grid;
  font-size: 12px;
  font-weight: 800;
  place-items: center;
}

.calendar-grid .today {
  background: var(--color-primary);
  color: #fff;
}

.event-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.event-list button {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-primary);
  cursor: pointer;
  font-weight: 800;
  min-height: 34px;
}

@keyframes progress-in {
  from {
    transform: scaleX(0);
    transform-origin: left;
  }
  to {
    transform: scaleX(1);
    transform-origin: left;
  }
}

@keyframes agent-pulse {
  0%,
  100% {
    opacity: 0.45;
    transform: scale(0.96);
  }
  50% {
    opacity: 0.9;
    transform: scale(1.08);
  }
}

@media (max-width: 1000px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .space-list {
    max-height: none;
  }

  .calendar-panel {
    max-width: 320px;
  }
}

@media (max-width: 640px) {
  .continue-actions,
  .section-heading,
  .dashboard-empty {
    align-items: stretch;
    flex-direction: column;
  }
}

/* Taste pass: GitHub-like dashboard density with quiet dividers instead of card piles. */
.dashboard-grid {
  grid-template-columns: minmax(310px, 360px) minmax(0, 1fr) minmax(240px, 286px);
  gap: 0;
  min-height: calc(100dvh - 92px);
  border-top: 1px solid rgba(161, 211, 202, 0.5);
}

.spaces-column {
  border-right: 1px solid rgba(161, 211, 202, 0.58);
  padding: 14px 14px 0 0;
}

.dashboard-main {
  padding: 14px 20px;
}

.calendar-column {
  border-left: 1px solid rgba(161, 211, 202, 0.58);
  padding: 14px 0 0 14px;
}

.dashboard-heading h1 {
  font-size: clamp(28px, 3vw, 42px);
  letter-spacing: 0;
  margin: 0;
}

.continue-panel,
.dashboard-stats .panel,
.calendar-panel {
  border-radius: 0;
  box-shadow: none;
}

.continue-panel {
  border: 0;
  border-top: 1px solid rgba(161, 211, 202, 0.55);
  border-bottom: 1px solid rgba(161, 211, 202, 0.55);
  background: linear-gradient(90deg, rgba(236, 253, 245, 0.65), rgba(255, 255, 255, 0.52));
}

.dashboard-stats {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.export-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.export-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.archived-panel {
  display: grid;
  gap: 10px;
}

.archived-heading {
  min-height: auto;
}

.archived-list {
  display: grid;
  gap: 8px;
}

.archived-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  border-top: 1px solid rgba(161, 211, 202, 0.42);
  padding-top: 10px;
}

.archived-row strong,
.archived-row small {
  display: block;
  overflow-wrap: anywhere;
}

.archived-row small {
  color: var(--color-muted);
  margin-top: 3px;
}

.dashboard-stats .panel {
  border: 0;
  border-top: 1px solid rgba(161, 211, 202, 0.55);
  background: transparent;
}

.space-list {
  gap: 0;
  max-height: calc(100dvh - 152px);
  padding-right: 0;
}

.space-row {
  border: 0;
  border-left: 3px solid transparent;
  border-bottom: 1px solid rgba(161, 211, 202, 0.36);
  border-radius: 0;
  background: transparent;
  padding: 12px 42px 12px 10px;
}

.space-row:hover,
.space-row.active {
  border-left-color: #14b8a6;
  box-shadow: none;
  background: rgba(255, 255, 255, 0.6);
  transform: none;
}

.space-row-delete {
  top: 10px;
  right: 8px;
  border-radius: 7px;
}

.space-row-continue {
  border-bottom: 1px solid currentColor;
  line-height: 1.2;
  text-decoration: none;
}

.calendar-panel {
  aspect-ratio: 1;
  border: 1px solid rgba(161, 211, 202, 0.58);
  background: rgba(255, 255, 255, 0.62);
}

@media (max-width: 1000px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .spaces-column,
  .calendar-column {
    border: 0;
    padding: 0;
  }

  .dashboard-main {
    padding-inline: 0;
  }

  .dashboard-stats {
    grid-template-columns: 1fr;
  }

  .export-panel,
  .archived-row {
    align-items: stretch;
    grid-template-columns: 1fr;
  }

  .export-panel,
  .export-actions {
    flex-direction: column;
  }
}
</style>
