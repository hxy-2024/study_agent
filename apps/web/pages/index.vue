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

const fallbackSpaces = computed(() => store.spaces.filter(space => space.status !== 'archived'))
const activeSpaces = computed(() => dashboard.value?.spaces ?? fallbackSpaces.value)
const currentSpace = computed(() => activeSpaces.value[0] ?? null)
const pendingActionCount = computed(() => dashboard.value?.pending_actions?.length ?? 0)
const pendingActionLabel = computed(() => `${pendingActionCount.value} ${pendingActionCount.value === 1 ? 'pending action' : 'pending actions'}`)
const supervisionRefreshCount = computed(() => dashboard.value?.supervision_refresh_count ?? 0)
const supervisionRefreshLabel = computed(() => {
  return `${supervisionRefreshCount.value} ${supervisionRefreshCount.value === 1 ? 'supervision refresh' : 'supervision refreshes'}`
})
const recentAgentRuns = computed(() => dashboard.value?.recent_agent_runs ?? [])
const progressPercent = computed(() => {
  if (!currentSpace.value) return 0
  return Math.max(12, Math.min(78, Math.round(100 / Math.max(1, currentSpace.value.target_days) * 7)))
})

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
    <div class="dashboard-layout">
      <div class="dashboard-main">
        <div class="topbar section-heading">
          <div>
            <p class="eyebrow">Workspace</p>
            <h1>Continue Learning</h1>
            <p>Pick up the next study task or create a focused space for new material.</p>
          </div>
          <NuxtLink class="primary-button" to="/spaces/new">New Study Space</NuxtLink>
        </div>

        <section v-if="store.loading" class="card skeleton" aria-label="Loading study spaces" />

        <section v-else-if="!currentSpace" class="card dashboard-empty">
          <div>
            <p class="eyebrow">Start here</p>
            <h2>Create your first study space</h2>
            <p>Set a goal, gather source material, and let the workspace organize the route.</p>
          </div>
          <NuxtLink class="primary-button" to="/spaces/new">New Study Space</NuxtLink>
        </section>

        <section v-else class="card continue-panel">
          <div class="continue-copy">
            <p class="eyebrow">Next action</p>
            <h2>{{ currentSpace.name }}</h2>
            <p>{{ currentSpace.goal }}</p>
            <div class="progress-track" aria-label="Current space progress">
              <span :style="{ width: `${progressPercent}%` }" />
            </div>
            <small>{{ progressPercent }}% route foundation prepared</small>
          </div>
          <div class="continue-actions">
            <span class="status-badge">{{ currentSpace.status }}</span>
            <NuxtLink class="primary-button" :to="`/spaces/${currentSpace.id}`">Continue</NuxtLink>
          </div>
        </section>

        <section v-if="activeSpaces.length" class="recent-section">
          <div class="section-heading compact">
            <div>
              <p class="eyebrow">Recent Spaces</p>
              <h2>{{ activeSpaces.length }} active spaces</h2>
            </div>
          </div>

          <div class="recent-grid">
            <NuxtLink v-for="space in activeSpaces" :key="space.id" class="card recent-card" :to="`/spaces/${space.id}`">
              <span class="status-badge">{{ space.status }}</span>
              <h3>{{ space.name }}</h3>
              <p>{{ space.goal }}</p>
              <small>{{ space.target_days }} target days</small>
            </NuxtLink>
          </div>
        </section>
      </div>

      <aside class="dashboard-rail">
        <section class="panel">
          <p class="eyebrow">Today</p>
          <h2>Study queue</h2>
          <p v-if="dashboardLoading">Loading local dashboard...</p>
          <p v-else>{{ pendingActionLabel }}</p>
          <p>{{ supervisionRefreshLabel }}</p>
          <NuxtLink
            v-if="currentSpace && pendingActionCount"
            class="secondary-button"
            :to="`/spaces/${currentSpace.id}`"
          >
            Review queue
          </NuxtLink>
        </section>

        <section class="panel mentor-panel">
          <p class="eyebrow">AI Mentor</p>
          <h2>{{ recentAgentRuns.length ? 'Recent runtime' : 'Ready for sources' }}</h2>
          <p v-if="recentAgentRuns.length">{{ recentAgentRuns[0].summary }}</p>
          <p v-else>Upload text or Markdown in a study space to prepare retrieval and route generation.</p>
        </section>

        <section class="metric-card">
          <p class="eyebrow">Weekly Progress</p>
          <strong>{{ activeSpaces.length }}</strong>
          <span>{{ activeSpaces.length === 1 ? 'active space' : 'active spaces' }}</span>
        </section>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.dashboard-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  gap: 18px;
  align-items: start;
}

.dashboard-main,
.dashboard-rail,
.recent-section {
  display: grid;
  gap: 18px;
}

.section-heading {
  min-height: 0;
}

.section-heading p,
.continue-panel p,
.dashboard-empty p,
.recent-card p,
.dashboard-rail p {
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

.dashboard-empty,
.continue-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
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

.recent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}

.recent-card {
  display: grid;
  gap: 8px;
}

.recent-card h3,
.recent-card p {
  overflow-wrap: anywhere;
}

.recent-card .status-badge {
  justify-self: start;
}

.metric-card strong {
  display: block;
  color: var(--color-primary);
  font-size: 28px;
  margin: 8px 0;
}

.mentor-panel {
  border-color: var(--color-border-strong);
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
  .dashboard-layout {
    grid-template-columns: 1fr;
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
