<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

type AnswerStyle = 'concise' | 'socratic' | 'exam_review' | 'code_tutor'
type WebSearchProvider = 'duckduckgo' | 'tavily'
type Locale = 'en-US' | 'zh-CN'
type SettingsCategory = 'general' | 'appearance' | 'configuration'

interface LocalSettingsResponse {
  llm_provider: string
  llm_base_url: string
  llm_model: string
  available_models: string[]
  llm_api_key: string
  llm_api_key_masked: string
  web_search_default_enabled: boolean
  web_search_provider: WebSearchProvider
  tavily_api_key: string
  tavily_api_key_masked: string
  answer_style: AnswerStyle
  locale: Locale
  main_agent_system_prompt: string
  session_tutor_system_prompt: string
  chapter_mentor_system_prompt: string
}

interface ModelRefreshResponse {
  models: string[]
  selected_model: string
}

const config = useRuntimeConfig()
const { setLocale, t } = useLocalI18n()
const activeCategory = ref<SettingsCategory>('general')
const loading = ref(false)
const saving = ref(false)
const refreshingModels = ref(false)
const error = ref('')
const toastMessage = ref('')
let toastTimer: ReturnType<typeof window.setTimeout> | null = null

const settings = reactive({
  provider: 'deterministic',
  baseUrl: 'https://api.openai.com/v1',
  apiKey: '',
  defaultModel: 'gpt-4.1-mini',
  availableModels: [] as string[],
  webSearchDefault: false,
  webSearchProvider: 'duckduckgo' as WebSearchProvider,
  tavilyApiKey: '',
  answerStyle: 'concise' as AnswerStyle,
  locale: 'zh-CN' as Locale,
  mainAgentSystemPrompt: '',
  sessionTutorSystemPrompt: '',
  chapterMentorSystemPrompt: ''
})

const copy = computed(() => {
  if (settings.locale === 'zh-CN') {
    return {
      title: '设置',
      subtitle: '管理本地个人运行时的模型、语言和 agent 行为。',
      general: '常规',
      appearance: '外观',
      configuration: '配置',
      provider: 'LLM provider',
      baseUrl: 'Base URL',
      apiKey: 'API key',
      defaultModel: 'Default model',
      refreshModels: '刷新模型',
      refreshingModels: '刷新中...',
      webSearchDefault: '默认开启联网补充',
      webSearchProvider: '联网服务',
      tavilyApiKey: 'Tavily API key',
      language: '语言',
      answerStyle: 'Answer style',
      mainAgentPrompt: '一层主 agent 系统提示词',
      sessionTutorPrompt: '二层会话监督 agent 系统提示词',
      chapterMentorPrompt: '三层章节协助 agent 系统提示词',
      save: '保存',
      saving: '保存中...',
      loading: '正在读取本地配置...',
      note: '配置保存在本机 .local/settings.json，不会上传到外部服务。',
      saved: '配置成功'
    }
  }
  return {
    title: 'Settings',
    subtitle: 'Manage the local personal runtime model, language, and agent behavior.',
    general: 'General',
    appearance: 'Appearance',
    configuration: 'Configuration',
    provider: 'LLM provider',
    baseUrl: 'Base URL',
    apiKey: 'API key',
    defaultModel: 'Default model',
    refreshModels: 'Refresh models',
    refreshingModels: 'Refreshing...',
    webSearchDefault: 'Enable web supplement by default',
    webSearchProvider: 'Web search provider',
    tavilyApiKey: 'Tavily API key',
    language: 'Language',
    answerStyle: 'Answer style',
    mainAgentPrompt: 'Layer 1 main agent system prompt',
    sessionTutorPrompt: 'Layer 2 session tutor system prompt',
    chapterMentorPrompt: 'Layer 3 chapter mentor system prompt',
    save: 'Save',
    saving: 'Saving...',
    loading: 'Loading local settings...',
    note: 'Settings are stored in local .local/settings.json and are not uploaded.',
    saved: 'Saved'
  }
})

const categories = computed(() => [
  { id: 'general' as const, label: copy.value.general },
  { id: 'appearance' as const, label: copy.value.appearance },
  { id: 'configuration' as const, label: copy.value.configuration }
])

function devAuthHeaders() {
  return {
    'X-User-Id': '00000000-0000-0000-0000-000000000002',
    'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
  }
}

function applyResponse(response: LocalSettingsResponse) {
  settings.provider = response.llm_provider
  settings.baseUrl = response.llm_base_url
  settings.defaultModel = response.llm_model
  settings.availableModels = response.available_models || []
  settings.apiKey = response.llm_api_key || ''
  settings.webSearchDefault = response.web_search_default_enabled
  settings.webSearchProvider = response.web_search_provider
  settings.tavilyApiKey = response.tavily_api_key || ''
  settings.answerStyle = response.answer_style
  settings.locale = response.locale || 'zh-CN'
  settings.mainAgentSystemPrompt = response.main_agent_system_prompt || ''
  settings.sessionTutorSystemPrompt = response.session_tutor_system_prompt || ''
  settings.chapterMentorSystemPrompt = response.chapter_mentor_system_prompt || ''
}

async function loadLocalSettings() {
  loading.value = true
  error.value = ''
  try {
    const response = await $fetch<LocalSettingsResponse>(`${config.public.apiBaseUrl}/local-settings/ai`, {
      headers: devAuthHeaders()
    })
    applyResponse(response)
    setLocale(response.locale || 'zh-CN')
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Unable to load local settings.'
  } finally {
    loading.value = false
  }
}

async function refreshModels() {
  refreshingModels.value = true
  error.value = ''
  try {
    const response = await $fetch<ModelRefreshResponse>(`${config.public.apiBaseUrl}/local-settings/ai/models`, {
      method: 'POST',
      headers: devAuthHeaders()
    })
    settings.availableModels = response.models
    settings.defaultModel = response.selected_model
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Unable to refresh models.'
  } finally {
    refreshingModels.value = false
  }
}

async function saveLocalSettings() {
  saving.value = true
  error.value = ''
  try {
    const response = await $fetch<LocalSettingsResponse>(`${config.public.apiBaseUrl}/local-settings/ai`, {
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
        answer_style: settings.answerStyle,
        locale: settings.locale,
        main_agent_system_prompt: settings.mainAgentSystemPrompt,
        session_tutor_system_prompt: settings.sessionTutorSystemPrompt,
        chapter_mentor_system_prompt: settings.chapterMentorSystemPrompt
      }
    })
    applyResponse(response)
    setLocale(response.locale || 'zh-CN')
    showToast(copy.value.saved)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Unable to save local settings.'
  } finally {
    saving.value = false
  }
}

function showToast(message: string) {
  toastMessage.value = message
  if (toastTimer) {
    window.clearTimeout(toastTimer)
  }
  toastTimer = window.setTimeout(() => {
    toastMessage.value = ''
    toastTimer = null
  }, 1600)
}

onMounted(loadLocalSettings)

onBeforeUnmount(() => {
  if (toastTimer) {
    window.clearTimeout(toastTimer)
  }
})
</script>

<template>
  <section class="settings-page page-enter">
    <aside class="settings-sidebar" :aria-label="copy.title">
      <div class="settings-sidebar-heading">
        <p class="eyebrow">{{ copy.title }}</p>
        <h1>{{ copy.title }}</h1>
      </div>
      <button
        v-for="category in categories"
        :key="category.id"
        class="settings-category-button"
        :class="{ active: activeCategory === category.id }"
        type="button"
        @click="activeCategory = category.id"
      >
        {{ category.label }}
      </button>
    </aside>

    <main class="settings-content">
      <header class="settings-page-header">
        <div>
          <p class="eyebrow">{{ t('settings.localRuntime') }}</p>
          <h2>{{ copy.title }}</h2>
          <p>{{ copy.subtitle }}</p>
        </div>
        <button
          class="primary-button"
          type="button"
          data-testid="save-local-settings"
          :disabled="saving"
          @click="saveLocalSettings"
        >
          {{ saving ? copy.saving : copy.save }}
        </button>
      </header>

      <p v-if="loading" class="settings-note">{{ copy.loading }}</p>
      <p v-else-if="error" class="settings-note">{{ error }}</p>
      <p v-else class="settings-note">{{ copy.note }}</p>

      <section v-if="activeCategory === 'general'" class="settings-section" :aria-label="copy.general">
        <label class="form-field">
          {{ copy.provider }}
          <input v-model="settings.provider" class="input" data-testid="settings-provider">
        </label>
        <label class="form-field">
          {{ copy.baseUrl }}
          <input v-model="settings.baseUrl" class="input" data-testid="settings-base-url" type="url">
        </label>
        <label class="form-field">
          {{ copy.apiKey }}
          <input v-model="settings.apiKey" class="input" data-testid="settings-api-key" type="password">
        </label>
        <div class="settings-model-row">
          <label class="form-field">
            {{ copy.defaultModel }}
            <select
              v-if="settings.availableModels.length"
              v-model="settings.defaultModel"
              class="select"
              data-testid="settings-llm-model"
            >
              <option v-for="model in settings.availableModels" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
            <input v-else v-model="settings.defaultModel" class="input" data-testid="settings-llm-model">
          </label>
          <button
            class="secondary-button settings-refresh-button"
            type="button"
            data-testid="refresh-models"
            :disabled="refreshingModels"
            @click="refreshModels"
          >
            {{ refreshingModels ? copy.refreshingModels : copy.refreshModels }}
          </button>
        </div>
        <label class="form-field settings-checkbox">
          <input v-model="settings.webSearchDefault" type="checkbox">
          {{ copy.webSearchDefault }}
        </label>
        <label class="form-field">
          {{ copy.webSearchProvider }}
          <select v-model="settings.webSearchProvider" class="select">
            <option value="duckduckgo">DuckDuckGo</option>
            <option value="tavily">Tavily</option>
          </select>
        </label>
        <label class="form-field">
          {{ copy.tavilyApiKey }}
          <input v-model="settings.tavilyApiKey" class="input" type="password">
        </label>
      </section>

      <section v-else-if="activeCategory === 'appearance'" class="settings-section" :aria-label="copy.appearance">
        <label class="form-field">
          {{ copy.language }}
          <select v-model="settings.locale" class="select" data-testid="settings-locale">
            <option value="zh-CN">中文</option>
            <option value="en-US">English</option>
          </select>
        </label>
      </section>

      <section v-else class="settings-section" :aria-label="copy.configuration">
        <label class="form-field">
          {{ copy.answerStyle }}
          <select v-model="settings.answerStyle" class="select" data-testid="settings-answer-style">
            <option value="concise">Concise</option>
            <option value="socratic">Socratic</option>
            <option value="exam_review">Exam review</option>
            <option value="code_tutor">Code tutor</option>
          </select>
        </label>
        <label class="form-field">
          {{ copy.mainAgentPrompt }}
          <textarea
            v-model="settings.mainAgentSystemPrompt"
            class="textarea settings-prompt-input"
            data-testid="settings-main-agent-prompt"
            rows="5"
          />
        </label>
        <label class="form-field">
          {{ copy.sessionTutorPrompt }}
          <textarea
            v-model="settings.sessionTutorSystemPrompt"
            class="textarea settings-prompt-input"
            data-testid="settings-session-tutor-prompt"
            rows="5"
          />
        </label>
        <label class="form-field">
          {{ copy.chapterMentorPrompt }}
          <textarea
            v-model="settings.chapterMentorSystemPrompt"
            class="textarea settings-prompt-input"
            data-testid="settings-chapter-mentor-prompt"
            rows="5"
          />
        </label>
      </section>

      <div
        v-if="toastMessage"
        class="settings-toast"
        role="status"
        aria-live="polite"
        data-testid="settings-success-toast"
      >
        {{ toastMessage }}
      </div>
    </main>
  </section>
</template>

