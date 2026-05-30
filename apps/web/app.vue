<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

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
const { loadLocale, t } = useLocalI18n()
const drawerOpen = ref(false)
const settingsOpen = ref(false)
const settingsLoading = ref(false)
const settingsSaving = ref(false)
const settingsError = ref('')
const settingsToastMessage = ref('')
let settingsToastTimer: ReturnType<typeof window.setTimeout> | null = null
const runtimeStatusOpen = ref(false)
const runtimeStatusLoading = ref(false)
const runtimeStatusError = ref('')
const runtimeStatus = ref<RuntimeStatus | null>(null)
type OverlayKey = 'drawer' | 'settings' | 'runtime'
const overlayPointerStartedOnBackdrop = reactive<Record<OverlayKey, boolean>>({
  drawer: false,
  settings: false,
  runtime: false
})

const settings = reactive({
  provider: 'deterministic',
  baseUrl: 'https://api.openai.com/v1',
  apiKey: '',
  defaultModel: 'gpt-4.1-mini',
  webSearchDefault: false,
  webSearchProvider: 'duckduckgo',
  tavilyApiKey: '',
  answerStyle: 'concise'
})

const navigationItems = computed(() => [
  { label: t('nav.home'), to: '/', enabled: true },
  { label: t('nav.library'), to: '/', enabled: false },
  { label: t('nav.reviews'), to: '/', enabled: false },
  { label: t('nav.progress'), to: '/', enabled: false },
  { label: t('nav.settings'), to: '/settings', enabled: true }
])

function devAuthHeaders() {
  return {
    'X-User-Id': '00000000-0000-0000-0000-000000000002',
    'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
  }
}

async function openNavigationItem(item: { action?: string; enabled?: boolean; to?: string }) {
  if (!item.enabled) return

  if (item.action === 'settings') {
    settingsOpen.value = true
    await loadLocalSettings()
  } else if (item.to) {
    await navigateTo(item.to)
  }
  drawerOpen.value = false
}

async function loadLocalSettings() {
  settingsLoading.value = true
  settingsError.value = ''
  try {
    const response = await $fetch<{
      llm_provider: string
      llm_base_url: string
      llm_model: string
      llm_api_key_masked: string
      web_search_default_enabled: boolean
      web_search_provider: string
      tavily_api_key_masked: string
      answer_style: string
    }>(`${config.public.apiBaseUrl}/local-settings/ai`, {
      headers: devAuthHeaders()
    })
    settings.provider = response.llm_provider
    settings.baseUrl = response.llm_base_url
    settings.defaultModel = response.llm_model
    settings.apiKey = ''
    settings.webSearchDefault = response.web_search_default_enabled
    settings.webSearchProvider = response.web_search_provider
    settings.tavilyApiKey = ''
    settings.answerStyle = response.answer_style
  } catch (error) {
    settingsError.value = error instanceof Error ? error.message : t('app.loadingSettings')
  } finally {
    settingsLoading.value = false
  }
}

async function saveLocalSettings() {
  settingsSaving.value = true
  settingsError.value = ''
  try {
    await $fetch(`${config.public.apiBaseUrl}/local-settings/ai`, {
      method: 'PUT',
      headers: devAuthHeaders(),
      body: {
        llm_provider: settings.provider,
        llm_base_url: settings.baseUrl,
        llm_model: settings.defaultModel,
        llm_api_key: settings.apiKey,
        web_search_default_enabled: settings.webSearchDefault,
        web_search_provider: settings.webSearchProvider,
        tavily_api_key: settings.tavilyApiKey,
        answer_style: settings.answerStyle
      }
    })
    settings.apiKey = ''
    showSettingsToast(t('app.saved'))
  } catch (error) {
    settingsError.value = error instanceof Error ? error.message : t('app.runtimeUnavailable')
  } finally {
    settingsSaving.value = false
  }
}

function showSettingsToast(message: string) {
  settingsToastMessage.value = message
  if (settingsToastTimer) {
    window.clearTimeout(settingsToastTimer)
  }
  settingsToastTimer = window.setTimeout(() => {
    settingsToastMessage.value = ''
    settingsToastTimer = null
  }, 1600)
}

async function openRuntimeStatus() {
  runtimeStatusOpen.value = true
  runtimeStatusLoading.value = true
  runtimeStatusError.value = ''
  try {
    runtimeStatus.value = await $fetch<RuntimeStatus>(`${config.public.apiBaseUrl}/runtime/status`)
  } catch (error) {
    runtimeStatus.value = null
    runtimeStatusError.value = error instanceof Error ? error.message : t('app.runtimeUnavailable')
  } finally {
    runtimeStatusLoading.value = false
  }
}

function trackOverlayPointerDown(event: PointerEvent, key: OverlayKey) {
  overlayPointerStartedOnBackdrop[key] = event.target === event.currentTarget
}

function closeOverlayFromBackdropClick(event: MouseEvent, key: OverlayKey, close: () => void) {
  if (event.target === event.currentTarget && overlayPointerStartedOnBackdrop[key]) {
    close()
  }
  overlayPointerStartedOnBackdrop[key] = false
}

function closeDrawer() {
  drawerOpen.value = false
}

function closeSettings() {
  settingsOpen.value = false
}

function closeRuntimeStatus() {
  runtimeStatusOpen.value = false
}

onMounted(() => {
  loadLocale()
})

onBeforeUnmount(() => {
  if (settingsToastTimer) {
    window.clearTimeout(settingsToastTimer)
  }
})
</script>

<template>
  <div class="app-shell">
    <header class="app-topbar" :aria-label="t('app.globalNavigation')">
      <div class="topbar-left">
        <button
          class="icon-button hamburger-button"
          type="button"
          :aria-label="t('app.openNavigation')"
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
          {{ t('app.localRuntime') }}
        </button>
      </div>

      <button class="avatar-button" type="button" :aria-label="t('app.localUserProfile')">U</button>
    </header>

    <div class="workspace-frame">
      <main class="main">
        <NuxtPage />
      </main>
    </div>

    <div
      v-if="drawerOpen"
      class="overlay"
      @pointerdown="trackOverlayPointerDown($event, 'drawer')"
      @click="closeOverlayFromBackdropClick($event, 'drawer', closeDrawer)"
    >
      <aside class="nav-drawer" :aria-label="t('app.globalNavigation')">
        <div class="drawer-heading">
          <div>
            <p class="eyebrow">{{ t('app.navigate') }}</p>
            <h2>{{ t('app.workspace') }}</h2>
          </div>
          <button class="icon-button" type="button" :aria-label="t('app.closeNavigation')" @click="drawerOpen = false">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6l12 12" />
              <path d="M18 6 6 18" />
            </svg>
          </button>
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

    <div
      v-if="settingsOpen"
      class="overlay"
      @pointerdown="trackOverlayPointerDown($event, 'settings')"
      @click="closeOverlayFromBackdropClick($event, 'settings', closeSettings)"
    >
      <section class="settings-modal" :aria-label="t('app.localSettings')">
        <div class="drawer-heading">
          <div>
            <p class="eyebrow">{{ t('app.settings') }}</p>
            <h2>{{ t('app.localModelDefaults') }}</h2>
          </div>
          <button class="icon-button" type="button" :aria-label="t('app.closeSettings')" @click="settingsOpen = false">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6l12 12" />
              <path d="M18 6 6 18" />
            </svg>
          </button>
        </div>

        <div class="settings-grid">
          <label class="form-field">
            {{ t('app.provider') }}
            <input v-model="settings.provider" class="input" placeholder="deterministic or openai-compatible">
          </label>
          <label class="form-field">
            {{ t('app.baseUrl') }}
            <input v-model="settings.baseUrl" class="input" type="url">
          </label>
          <label class="form-field">
            {{ t('app.apiKey') }}
            <input v-model="settings.apiKey" class="input" type="password" placeholder="Optional for local providers">
          </label>
          <label class="form-field">
            {{ t('app.defaultModel') }}
            <input v-model="settings.defaultModel" class="input">
          </label>
          <label class="form-field">
            {{ t('app.answerStyle') }}
            <select v-model="settings.answerStyle" class="input">
              <option value="concise">Concise</option>
              <option value="socratic">Socratic</option>
              <option value="exam_review">Exam review</option>
              <option value="code_tutor">Code tutor</option>
            </select>
          </label>
          <label class="form-field settings-checkbox">
            <input v-model="settings.webSearchDefault" type="checkbox">
            {{ t('app.webSearchDefault') }}
          </label>
          <label class="form-field">
            {{ t('app.webSearchProvider') }}
            <select v-model="settings.webSearchProvider" class="input">
              <option value="duckduckgo">DuckDuckGo</option>
              <option value="tavily">Tavily</option>
            </select>
          </label>
          <label class="form-field">
            {{ t('app.tavilyApiKey') }}
            <input v-model="settings.tavilyApiKey" class="input" type="password" placeholder="Optional unless Tavily is selected">
          </label>
        </div>

        <p v-if="settingsLoading" class="settings-note">{{ t('app.loadingSettings') }}</p>
        <p v-else-if="settingsError" class="settings-note">{{ settingsError }}</p>
        <p v-else class="settings-note">{{ t('app.settingsNote') }}</p>
        <button
          class="primary-button"
          type="button"
          data-testid="save-local-settings"
          :disabled="settingsSaving"
          @click="saveLocalSettings"
        >
          {{ settingsSaving ? t('app.saving') : t('app.save') }}
        </button>
        <div
          v-if="settingsToastMessage"
          class="settings-toast"
          role="status"
          aria-live="polite"
          data-testid="settings-success-toast"
        >
          {{ settingsToastMessage }}
        </div>
      </section>
    </div>

    <div
      v-if="runtimeStatusOpen"
      class="overlay"
      @pointerdown="trackOverlayPointerDown($event, 'runtime')"
      @click="closeOverlayFromBackdropClick($event, 'runtime', closeRuntimeStatus)"
    >
      <section class="settings-modal runtime-status-modal" :aria-label="t('app.localRuntime')">
        <div class="drawer-heading">
          <div>
            <p class="eyebrow">{{ t('app.runtime') }}</p>
            <h2>{{ t('app.localStatus') }}</h2>
          </div>
          <button class="icon-button" type="button" :aria-label="t('app.closeRuntime')" @click="runtimeStatusOpen = false">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6l12 12" />
              <path d="M18 6 6 18" />
            </svg>
          </button>
        </div>

        <p v-if="runtimeStatusLoading" class="settings-note">{{ t('app.checkingServices') }}</p>
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
