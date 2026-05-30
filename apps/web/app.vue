<script setup lang="ts">
import { reactive, ref } from 'vue'

interface RuntimeCheck {
  name: string
  status: 'ok' | 'warning' | 'error' | string
  detail: string
}

interface RuntimeStatus {
  status: 'ok' | 'warning' | 'degraded' | string
  checks: RuntimeCheck[]
}

const config = useRuntimeConfig()
const drawerOpen = ref(false)
const settingsOpen = ref(false)
const runtimeStatusOpen = ref(false)
const runtimeStatusLoading = ref(false)
const runtimeStatusError = ref('')
const runtimeStatus = ref<RuntimeStatus | null>(null)

const settings = reactive({
  baseUrl: 'http://127.0.0.1:8000/api/v1',
  apiKey: '',
  defaultModel: 'gpt-4.1-mini',
  embeddingModel: ''
})

const navigationItems = [
  { label: 'Home', to: '/', enabled: true },
  { label: 'Library', to: '/', enabled: false },
  { label: 'Reviews', to: '/', enabled: false },
  { label: 'Progress', to: '/', enabled: false },
  { label: 'Settings', to: '/', enabled: true, action: 'settings' }
]

async function openNavigationItem(item: { action?: string; enabled?: boolean; to?: string }) {
  if (!item.enabled) return

  if (item.action === 'settings') {
    settingsOpen.value = true
  } else if (item.to) {
    await navigateTo(item.to)
  }
  drawerOpen.value = false
}

async function openRuntimeStatus() {
  runtimeStatusOpen.value = true
  runtimeStatusLoading.value = true
  runtimeStatusError.value = ''
  try {
    runtimeStatus.value = await $fetch<RuntimeStatus>(`${config.public.apiBaseUrl}/runtime/status`)
  } catch (error) {
    runtimeStatus.value = null
    runtimeStatusError.value = error instanceof Error ? error.message : 'Runtime status is unavailable.'
  } finally {
    runtimeStatusLoading.value = false
  }
}
</script>

<template>
  <div class="app-shell">
    <header class="app-topbar" aria-label="Global navigation">
      <div class="topbar-left">
        <button
          class="icon-button hamburger-button"
          type="button"
          aria-label="Open navigation"
          :aria-expanded="drawerOpen"
          @click="drawerOpen = true"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 7h14" />
            <path d="M5 12h14" />
            <path d="M5 17h14" />
          </svg>
        </button>

        <NuxtLink class="brand-mark" to="/">
        <span class="brand-icon">S</span>
          <strong>study_agent</strong>
        </NuxtLink>
      </div>

      <div class="topbar-center">
        <button
          class="runtime-pill runtime-status-button"
          type="button"
          data-testid="runtime-status-button"
          @click="openRuntimeStatus"
        >
          Local runtime
        </button>
      </div>

      <button class="avatar-button" type="button" aria-label="Local user profile">U</button>
    </header>

    <div class="workspace-frame">
      <main class="main">
        <NuxtPage />
      </main>
    </div>

    <div v-if="drawerOpen" class="overlay" @click.self="drawerOpen = false">
      <aside class="nav-drawer" aria-label="Primary navigation">
        <div class="drawer-heading">
          <div>
            <p class="eyebrow">Navigate</p>
            <h2>Workspace</h2>
          </div>
          <button class="icon-button" type="button" aria-label="Close navigation" @click="drawerOpen = false">×</button>
        </div>

        <nav class="drawer-nav">
          <button
            v-for="item in navigationItems"
            :key="item.label"
            class="nav-link"
            :class="{ disabled: !item.enabled }"
            :aria-disabled="!item.enabled"
            type="button"
            @click="openNavigationItem(item)"
          >
            {{ item.label }}
          </button>
        </nav>
      </aside>
    </div>

    <div v-if="settingsOpen" class="overlay" @click.self="settingsOpen = false">
      <section class="settings-modal" aria-label="Local settings">
        <div class="drawer-heading">
          <div>
            <p class="eyebrow">Settings</p>
            <h2>Local model defaults</h2>
          </div>
          <button class="icon-button" type="button" aria-label="Close settings" @click="settingsOpen = false">×</button>
        </div>

        <div class="settings-grid">
          <label class="form-field">
            Base URL
            <input v-model="settings.baseUrl" class="input" type="url">
          </label>
          <label class="form-field">
            API key
            <input v-model="settings.apiKey" class="input" type="password" placeholder="Optional for local providers">
          </label>
          <label class="form-field">
            Default model
            <input v-model="settings.defaultModel" class="input">
          </label>
          <label class="form-field">
            Embedding model
            <input v-model="settings.embeddingModel" class="input" placeholder="Optional">
          </label>
        </div>

        <p class="settings-note">These defaults stay local in this browser for now. Account editing remains reserved.</p>
        <button class="primary-button" type="button" @click="settingsOpen = false">Done</button>
      </section>
    </div>

    <div v-if="runtimeStatusOpen" class="overlay" @click.self="runtimeStatusOpen = false">
      <section class="settings-modal runtime-status-modal" aria-label="Local runtime status">
        <div class="drawer-heading">
          <div>
            <p class="eyebrow">Runtime</p>
            <h2>Local status</h2>
          </div>
          <button class="icon-button" type="button" aria-label="Close runtime status" @click="runtimeStatusOpen = false">脳</button>
        </div>

        <p v-if="runtimeStatusLoading" class="settings-note">Checking local services...</p>
        <p v-else-if="runtimeStatusError" class="settings-note">{{ runtimeStatusError }}</p>
        <div v-else-if="runtimeStatus" class="runtime-status-list">
          <article
            v-for="check in runtimeStatus.checks"
            :key="check.name"
            class="runtime-status-row"
            :class="`runtime-status-${check.status}`"
          >
            <span class="runtime-status-dot" aria-hidden="true" />
            <div>
              <strong>{{ check.name.replace('_', ' ') }}</strong>
              <p>{{ check.detail }}</p>
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>
