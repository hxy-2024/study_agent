<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

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

interface DashboardSummary {
  spaces: DashboardSpace[]
  pending_actions: DashboardAction[]
  supervision_refresh_count: number
  recent_agent_runs: DashboardAgentRun[]
}

const dashboard = ref<DashboardSummary | null>(null)
const dashboardLoading = ref(false)
const spaceSearch = ref('')
const selectedSpaceId = ref('')

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
const continueChapterId = computed(() => {
  if (!currentSpace.value) return null
  return dashboard.value?.pending_actions.find(action => {
    return action.study_space_id === currentSpace.value?.id && Boolean(action.chapter_id)
  })?.chapter_id ?? null
})
const continueHref = computed(() => continueChapterId.value ? `/chapters/${continueChapterId.value}` : '/spaces/new')
const continueLabel = computed(() => continueChapterId.value ? 'Continue' : 'Prepare route')
const today = new Date()
const currentDay = today.getDate()
const calendarDays = Array.from({ length: 35 }, (_, index) => index + 1)
const progressPercent = computed(() => {
  if (!currentSpace.value) return 0
  return Math.max(12, Math.min(78, Math.round(100 / Math.max(1, currentSpace.value.target_days) * 7)))
})

function selectSpace(spaceId: string) {
  selectedSpaceId.value = spaceId
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

onMounted(() => {
  store.loadSpaces()
  loadDashboard()
})
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
          <button
            v-for="space in visibleSpaces"
            :key="space.id"
            class="space-row"
            :class="{ active: currentSpace?.id === space.id }"
            type="button"
            @click="selectSpace(space.id)"
          >
            <span>
              <strong>{{ space.name }}</strong>
              <small>{{ space.goal }}</small>
            </span>
            <span class="status-badge">{{ space.status }}</span>
          </button>
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
            <p class="eyebrow">Continue</p>
            <h2>{{ currentSpace.name }}</h2>
            <p>{{ currentSpace.goal }}</p>
            <div class="progress-track" aria-label="Current space progress">
              <span :style="{ width: `${progressPercent}%` }" />
            </div>
            <small>{{ progressPercent }}% route foundation prepared · {{ currentSpace.target_days }} target days</small>
          </div>
          <div class="continue-actions">
            <span class="status-badge">{{ currentSpace.status }}</span>
            <NuxtLink class="primary-button" :to="continueHref">{{ continueLabel }}</NuxtLink>
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
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.88);
  color: var(--color-text);
  cursor: pointer;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  padding: 12px;
  text-align: left;
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

.space-row small {
  color: var(--color-muted);
  margin-top: 4px;
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
</style>
