<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const { loadLocale, t } = useLocalI18n()
const studySpacesStore = useStudySpacesStore()

type RouteChapter = {
  id?: string
  order: number
  title: string
  description: string
  estimated_days: number
}

type CreatedSpace = {
  id: string
}

type UploadedSource = {
  source: {
    id: string
  }
}

type IngestResult = {
  status: string
  chunk_count: number
}

type SourceChunk = {
  id: string
  chunk_index: number
  text: string
  citation: Record<string, unknown>
}

type SourceChunkList = {
  chunks: SourceChunk[]
}

type RouteDraftResponse = {
  chapters: Array<{
    id: string
    order_index: number
    title: string
    goal: string
    summary: string
    estimated_days: number
  }>
}

type LocalSettingsResponse = {
  llm_model?: string
  available_models?: string[]
  embedding_model?: string
}

const form = reactive({
  name: '',
  goal: '',
  level: 'beginner',
  intensity: 'normal',
  target_days: 30
})

const modelSettings = reactive({
  embeddingPreset: 'local-deterministic'
})

const material = reactive({
  filename: 'learning-material.md',
  content: ''
})

const DEV_AUTH_HEADERS = {
  'X-User-Id': '00000000-0000-0000-0000-000000000002',
  'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
}

const createdSpaceId = ref('')
const sourceId = ref('')
const routeOutline = ref<RouteChapter[]>([])
const routeDraftText = ref('')
const materialChunks = ref<SourceChunk[]>([])
const showChunkModal = ref(false)
const showChapterModal = ref(false)
const generatingDetails = ref(false)
const runningRag = ref(false)
const generatingRoute = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const selectedChapter = ref(0)
const configuredModel = ref('')
const configuredEmbeddingModel = ref('')
const configuredModels = ref<string[]>([])
const createLayoutRef = ref<HTMLFormElement | null>(null)
const formColumnPercent = ref(50)
const resizingLayout = ref(false)

const chapterDetails = ref<RouteChapter[]>([
  {
    order: 1,
    title: '目标拆解',
    description: '明确范围、前置知识、完成标准和每日学习节奏。',
    estimated_days: 2
  },
  {
    order: 2,
    title: '概念地图',
    description: '把上传资料整理成章节结构，并标记概念依赖。',
    estimated_days: 4
  },
  {
    order: 3,
    title: '练习强化',
    description: '围绕章节目标生成复习提示、测验和薄弱点追踪任务。',
    estimated_days: 2
  }
])

const selectedChapterDetail = computed(() => {
  return chapterDetails.value[selectedChapter.value] ?? chapterDetails.value[0] ?? {
    order: 1,
    title: t('create.chapterDetail'),
    description: t('create.emptyRoute'),
    estimated_days: 1
  }
})

const canRunRag = computed(() => {
  return Boolean(form.name.trim() && form.goal.trim() && material.content.trim() && !hasDuplicateName.value)
})

const normalizedSpaceName = computed(() => form.name.trim().toLowerCase())
const hasDuplicateName = computed(() => {
  if (!normalizedSpaceName.value) return false
  return studySpacesStore.spaces.some(space => space.name.trim().toLowerCase() === normalizedSpaceName.value)
})
const nameValidationMessage = computed(() => (hasDuplicateName.value ? t('create.duplicateName') : ''))

const canGenerateRoute = computed(() => {
  return Boolean(form.name.trim() && form.goal.trim() && !hasDuplicateName.value)
})

const createLayoutStyle = computed(() => ({
  '--form-column-percent': `${formColumnPercent.value}%`
}))

function backendErrorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null && 'data' in error) {
    const data = (error as { data?: { detail?: unknown } }).data
    if (typeof data?.detail === 'string' && data.detail.trim()) {
      return data.detail
    }
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

function isEmbeddingModel(model: string) {
  const normalized = model.trim().toLowerCase()
  return ['embedding', 'embed', 'bge', 'gte', 'jina', 'e5-'].some(marker => normalized.includes(marker))
}

const embeddingPresetOptions = computed(() => {
  const options = [
    {
      value: 'local-deterministic',
      label: t('create.localChunkEmbeddings')
    }
  ]
  const uniqueModels = Array.from(
    new Set([configuredEmbeddingModel.value, configuredModel.value, ...configuredModels.value].filter(Boolean))
  ).filter(isEmbeddingModel)
  for (const model of uniqueModels) {
    options.push({
      value: `configured:${model}`,
      label: model === configuredModel.value ? `${t('create.currentDefaultModel')}: ${model}` : model
    })
  }
  return options
})

async function loadLocalModelSettings() {
  const config = useRuntimeConfig()
  try {
    const response = await $fetch<LocalSettingsResponse>(`${config.public.apiBaseUrl}/local-settings/ai`, {
      headers: DEV_AUTH_HEADERS
    })
    configuredModel.value = response.llm_model || ''
    configuredEmbeddingModel.value = response.embedding_model || ''
    configuredModels.value = response.available_models || []
    if (response.embedding_model && isEmbeddingModel(response.embedding_model)) {
      modelSettings.embeddingPreset = `configured:${response.embedding_model}`
    }
  } catch {
    configuredModel.value = ''
    configuredEmbeddingModel.value = ''
    configuredModels.value = []
  }
}

function syncRouteDraftText(chapters: RouteChapter[]) {
  routeDraftText.value = chapters
    .map((chapter) => {
      return `${chapter.order}. ${chapter.title} (${chapter.estimated_days} days)\n${chapter.description}`
    })
    .join('\n\n')
}

async function handleMaterialFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  material.filename = file.name
  material.content = await file.text()
}

async function ensureSpace() {
  if (createdSpaceId.value) return createdSpaceId.value
  if (hasDuplicateName.value) {
    throw new Error(t('create.duplicateName'))
  }
  const config = useRuntimeConfig()
  const created = await $fetch<CreatedSpace>(`${config.public.apiBaseUrl}/study-spaces`, {
    method: 'POST',
    headers: DEV_AUTH_HEADERS,
    body: {
      ...form
    }
  })
  createdSpaceId.value = created.id
  return created.id
}

async function createRouteDraft(studySpaceId: string) {
  const config = useRuntimeConfig()
  const draft = await $fetch<RouteDraftResponse>(
    `${config.public.apiBaseUrl}/study-spaces/${studySpaceId}/route-drafts`,
    {
      method: 'POST',
      headers: DEV_AUTH_HEADERS,
      body: { max_chapters: 5 }
    }
  )
  routeOutline.value = draft.chapters.map(chapter => ({
    id: chapter.id,
    order: chapter.order_index,
    title: chapter.title,
    description: chapter.summary || chapter.goal,
    estimated_days: chapter.estimated_days
  }))
  chapterDetails.value = [...routeOutline.value]
  syncRouteDraftText(routeOutline.value)
}

async function generateRouteDraft() {
  if (hasDuplicateName.value) {
    errorMessage.value = t('create.duplicateName')
    return
  }
  if (!form.name.trim() || !form.goal.trim()) {
    errorMessage.value = t('create.fillRoute')
    return
  }
  generatingRoute.value = true
  errorMessage.value = ''
  try {
    const studySpaceId = await ensureSpace()
    await createRouteDraft(studySpaceId)
  } catch (error) {
    errorMessage.value = backendErrorMessage(error, t('create.routeFailed'))
  } finally {
    generatingRoute.value = false
  }
}

async function runRag() {
  if (!canRunRag.value) {
    errorMessage.value = hasDuplicateName.value ? t('create.duplicateName') : t('create.fillRag')
    return
  }
  const config = useRuntimeConfig()
  runningRag.value = true
  errorMessage.value = ''
  try {
    const studySpaceId = await ensureSpace()
    const uploaded = await $fetch<UploadedSource>(`${config.public.apiBaseUrl}/sources/from-text`, {
      method: 'POST',
      headers: DEV_AUTH_HEADERS,
      body: {
        study_space_id: studySpaceId,
        filename: material.filename || 'learning-material.md',
        content_type: 'text/markdown',
        content: material.content
      }
    })
    sourceId.value = uploaded.source.id
    await $fetch<IngestResult>(`${config.public.apiBaseUrl}/ingestion/sources/${sourceId.value}/run`, {
      method: 'POST',
      headers: DEV_AUTH_HEADERS,
      body: {
        embedding_preset: modelSettings.embeddingPreset
      }
    })
    const chunks = await $fetch<SourceChunkList>(`${config.public.apiBaseUrl}/sources/${sourceId.value}/chunks`, {
      headers: DEV_AUTH_HEADERS
    })
    materialChunks.value = chunks.chunks
    await createRouteDraft(studySpaceId)
  } catch (error) {
    errorMessage.value = backendErrorMessage(error, t('create.ragFailed'))
  } finally {
    runningRag.value = false
  }
}

async function generateChapterDetails() {
  generatingDetails.value = true
  showChapterModal.value = false
  errorMessage.value = ''
  try {
    await new Promise(resolve => window.setTimeout(resolve, 10))
    if (!routeOutline.value.length) {
      if (canRunRag.value) {
        await runRag()
      } else {
        await generateRouteDraft()
      }
    }
    chapterDetails.value = routeOutline.value.length ? [...routeOutline.value] : [...chapterDetails.value]
    selectedChapter.value = 0
    showChapterModal.value = true
  } finally {
    generatingDetails.value = false
  }
}

async function confirmChapterDetails() {
  const router = useRouter()
  submitting.value = true
  errorMessage.value = ''
  try {
    if (!createdSpaceId.value) {
      await ensureSpace()
    }
    if (!routeOutline.value.length && createdSpaceId.value) {
      await createRouteDraft(createdSpaceId.value)
    }
    const firstChapterId = chapterDetails.value[0]?.id ?? routeOutline.value[0]?.id
    if (!firstChapterId) {
      throw new Error(t('create.notReady'))
    }
    await router.push(`/chapters/${firstChapterId}`)
  } catch (error) {
    errorMessage.value = backendErrorMessage(error, t('create.enterFailed'))
  } finally {
    submitting.value = false
  }
}

function clampFormColumnPercent(value: number) {
  return Math.min(68, Math.max(42, value))
}

function updateFormColumnFromPointer(clientX: number) {
  const layout = createLayoutRef.value
  if (!layout) return
  const rect = layout.getBoundingClientRect()
  if (rect.width <= 0) return
  const nextPercent = ((clientX - rect.left) / rect.width) * 100
  formColumnPercent.value = clampFormColumnPercent(nextPercent)
}

function stopLayoutResize() {
  resizingLayout.value = false
  window.removeEventListener('pointermove', handleLayoutResize)
  window.removeEventListener('pointerup', stopLayoutResize)
}

function handleLayoutResize(event: PointerEvent) {
  if (!resizingLayout.value) return
  updateFormColumnFromPointer(event.clientX)
}

function startLayoutResize(event: PointerEvent) {
  if (window.matchMedia('(max-width: 1000px)').matches) return
  resizingLayout.value = true
  updateFormColumnFromPointer(event.clientX)
  window.addEventListener('pointermove', handleLayoutResize)
  window.addEventListener('pointerup', stopLayoutResize)
}

function adjustLayoutWithKeyboard(event: KeyboardEvent) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  formColumnPercent.value = clampFormColumnPercent(
    formColumnPercent.value + (event.key === 'ArrowRight' ? 2 : -2)
  )
}

onMounted(async () => {
  await loadLocale()
  await Promise.all([loadLocalModelSettings(), studySpacesStore.loadSpaces()])
})

onBeforeUnmount(stopLayoutResize)
</script>

<template>
  <section class="create-space page-enter">
    <div class="create-shell">
      <header class="create-header">
        <NuxtLink data-testid="back-home" class="back-link" to="/" :aria-label="t('common.back')">
          <span aria-hidden="true">←</span>
        </NuxtLink>
        <div>
          <h1>{{ t('create.title') }}</h1>
          <p>{{ t('create.subtitle') }}</p>
        </div>
      </header>

      <form
        ref="createLayoutRef"
        class="create-layout"
        :class="{ resizing: resizingLayout }"
        :style="createLayoutStyle"
        @submit.prevent="generateChapterDetails"
      >
        <main class="form-stack">
          <section class="card form-panel">
            <div class="section-heading step-inline-heading">
              <p class="eyebrow">{{ t('create.step1') }}</p>
              <h2>{{ t('create.spaceGoal') }}</h2>
            </div>

            <label class="form-field">
              {{ t('create.spaceName') }}
              <input
                v-model="form.name"
                name="space-name"
                class="input"
                :class="{ invalid: hasDuplicateName }"
                required
                maxlength="160"
                :aria-invalid="hasDuplicateName"
                aria-describedby="space-name-error"
              >
              <small v-if="nameValidationMessage" id="space-name-error" class="field-error">
                {{ nameValidationMessage }}
              </small>
            </label>

            <label class="form-field">
              {{ t('create.learningGoal') }}
              <textarea v-model="form.goal" name="learning-goal" class="textarea" required rows="4" />
            </label>

            <div class="field-grid target-days-grid">
              <label class="form-field">
                {{ t('create.targetDays') }}
                <input v-model.number="form.target_days" class="input" type="number" min="1" max="365">
              </label>
            </div>
          </section>

          <section class="card form-panel">
            <div class="section-heading split">
              <div class="step-inline-heading">
                <p class="eyebrow">{{ t('create.step2') }}</p>
                <h2>{{ t('create.materialRag') }}</h2>
              </div>
              <button
                data-testid="open-chunk-modal"
                class="secondary-button"
                type="button"
                :disabled="!materialChunks.length"
                @click="showChunkModal = true"
              >
                {{ t('create.viewChunks') }}
              </button>
            </div>

            <label class="upload-zone">
              <span>{{ t('create.upload') }}</span>
              <small>{{ material.filename }}</small>
              <input type="file" accept=".md,.txt,text/markdown,text/plain" @change="handleMaterialFile">
            </label>

            <label class="form-field">
              {{ t('create.pasteMaterial') }}
              <textarea v-model="material.content" class="textarea" rows="7" :placeholder="t('create.pastePlaceholder')" />
            </label>

            <div class="field-grid two">
              <label class="form-field">
                {{ t('create.embeddingPreset') }}
                <select v-model="modelSettings.embeddingPreset" class="select" data-testid="embedding-preset">
                  <option
                    v-for="option in embeddingPresetOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <button
              data-testid="run-rag"
              class="primary-button rag-button"
              type="button"
              :disabled="runningRag || !canRunRag"
                @click="runRag"
              >
                {{ runningRag ? t('create.runningIngestion') : t('create.runIngestion') }}
              </button>
            </div>
          </section>
        </main>

        <div
          class="layout-resizer"
          role="separator"
          aria-orientation="vertical"
          :aria-valuenow="Math.round(formColumnPercent)"
          aria-valuemin="42"
          aria-valuemax="68"
          tabindex="0"
          @keydown="adjustLayoutWithKeyboard"
          @pointerdown.prevent="startLayoutResize"
        />

        <aside class="route-panel">
          <div class="route-heading">
            <div>
              <p class="eyebrow">{{ t('create.step3') }}</p>
              <h2>{{ t('create.routeOutline') }}</h2>
            </div>
            <button
              class="secondary-button"
              type="button"
              data-testid="generate-route"
              :disabled="generatingRoute || !canGenerateRoute"
              @click="generateRouteDraft"
            >
              {{ generatingRoute ? t('common.generating') : t('create.generateRoute') }}
            </button>
          </div>

          <textarea
            v-if="routeDraftText"
            v-model="routeDraftText"
            class="textarea route-textarea"
            :aria-label="t('create.editableRoute')"
          />
          <div v-else class="empty-route">
            <p>{{ t('create.emptyRoute') }}</p>
          </div>

          <ol v-if="routeOutline.length" class="route-list">
            <li v-for="chapter in routeOutline" :key="`${chapter.order}-${chapter.title}`">
              <strong>{{ chapter.title }}</strong>
              <small>{{ chapter.estimated_days }} {{ t('create.days') }}</small>
            </li>
          </ol>

          <button
            data-testid="generate-chapter-details"
            class="primary-button detail-button"
            type="submit"
            :disabled="generatingDetails || runningRag || hasDuplicateName"
          >
            {{ generatingDetails ? t('create.generatingDetails') : t('create.generateDetails') }}
          </button>

          <p v-if="generatingRoute" class="loading-copy">{{ t('create.generatingRoute') }}</p>
          <p v-if="generatingDetails" class="loading-copy">{{ t('create.generatingDetails') }}</p>
          <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>
        </aside>
      </form>
    </div>

    <div v-if="showChunkModal" data-testid="chunk-modal" class="modal-backdrop">
      <section class="modal-card chunk-card" role="dialog" aria-modal="true" aria-labelledby="chunk-title">
        <button
          data-testid="close-chunk-modal"
          class="modal-close"
          type="button"
          :aria-label="t('common.close')"
          @click="showChunkModal = false"
        >
          ×
        </button>
        <p class="eyebrow">{{ t('create.ragPreview') }}</p>
        <h2 id="chunk-title">{{ t('create.embeddedChunks') }}</h2>
        <div class="chunk-list">
          <article v-for="chunk in materialChunks" :key="chunk.id">
            <strong>{{ t('create.chunk') }} {{ chunk.chunk_index + 1 }}</strong>
            <p>{{ chunk.text }}</p>
          </article>
        </div>
      </section>
    </div>

    <div v-if="showChapterModal" data-testid="chapter-modal" class="modal-backdrop">
      <section class="modal-card chapter-card" role="dialog" aria-modal="true" aria-labelledby="chapter-title">
        <button class="chapter-back" type="button" @click="showChapterModal = false">
          <span aria-hidden="true">←</span>
          {{ t('common.back') }}
        </button>

        <div class="chapter-layout">
          <aside class="chapter-list">
            <p class="eyebrow">{{ t('create.chapters') }}</p>
            <button
              v-for="(chapter, index) in chapterDetails"
              :key="`${chapter.order}-${chapter.title}`"
              type="button"
              :class="{ active: selectedChapter === index }"
              @click="selectedChapter = index"
            >
              {{ chapter.title }}
            </button>
          </aside>

          <article class="chapter-detail">
            <p class="eyebrow">{{ t('create.chapterDetail') }}</p>
            <h2 id="chapter-title">{{ selectedChapterDetail.title }}</h2>
            <p>{{ selectedChapterDetail.description }}</p>
          </article>
        </div>

        <button
          data-testid="confirm-chapter-details"
          class="primary-button confirm-button"
          type="button"
          :disabled="submitting"
          @click="confirmChapterDetails"
        >
          {{ submitting ? t('create.entering') : t('create.confirmEnter') }}
        </button>
      </section>
    </div>
  </section>
</template>

<style scoped>
.create-shell {
  display: grid;
  gap: 20px;
}

.create-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.create-header h1,
.section-heading h2,
.route-heading h2,
.modal-card h2 {
  margin: 0;
}

.create-header p,
.empty-route p,
.chunk-list p,
.chapter-detail p {
  color: var(--color-muted);
}

.back-link {
  display: inline-grid;
  width: 42px;
  height: 42px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  place-items: center;
  background: var(--color-surface);
  color: var(--color-text);
  font-size: 24px;
  font-weight: 900;
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

.create-layout {
  --form-column-percent: 50%;
  display: grid;
  grid-template-columns: minmax(360px, var(--form-column-percent)) 10px minmax(320px, 1fr);
  gap: 14px;
  align-items: start;
}

.layout-resizer {
  align-self: stretch;
  min-height: calc(100dvh - 170px);
  cursor: col-resize;
  position: relative;
  touch-action: none;
}

.layout-resizer::before {
  content: "";
  position: absolute;
  inset: 0 4px;
  border-radius: 999px;
  background: var(--color-border);
}

.layout-resizer:hover::before,
.layout-resizer:focus-visible::before,
.create-layout.resizing .layout-resizer::before {
  background: var(--color-primary);
}

.form-stack,
.form-panel,
.route-panel {
  display: grid;
  gap: 16px;
}

.section-heading.split,
.route-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.target-days-grid {
  grid-template-columns: minmax(180px, 280px);
}

.field-grid.two {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
}

.upload-zone {
  display: grid;
  gap: 5px;
  border: 1px dashed var(--color-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--color-primary-soft) 38%, transparent);
  cursor: pointer;
  padding: 20px;
}

.upload-zone span {
  color: var(--color-text);
  font-weight: 900;
}

.upload-zone small {
  color: var(--color-muted);
}

.upload-zone input {
  width: 100%;
}

.rag-button {
  min-height: 42px;
}

.route-panel {
  position: sticky;
  top: 76px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
  padding: 18px;
}

.route-textarea {
  min-height: 230px;
}

.empty-route {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
}

.route-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding-left: 22px;
}

.route-list li::marker {
  color: var(--color-primary);
  font-weight: 800;
}

.route-list li {
  color: var(--color-text);
}

.route-list small {
  display: block;
  color: var(--color-primary);
  font-weight: 800;
}

.detail-button {
  justify-self: stretch;
}

.loading-copy {
  margin: 0;
  color: var(--color-primary);
  font-weight: 900;
  text-align: center;
}

.modal-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgb(15 23 42 / 58%);
  padding: 22px;
}

.modal-card {
  position: relative;
  width: min(760px, 100%);
  max-height: 82vh;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: 0 24px 80px rgb(15 23 42 / 28%);
  padding: 24px;
}

.chunk-card {
  min-height: 420px;
}

.modal-close {
  position: absolute;
  top: 14px;
  right: 14px;
  border: 0;
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  font-size: 30px;
  line-height: 1;
}

.chunk-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.chunk-list article {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px;
}

.chapter-card {
  display: grid;
  width: min(1080px, 100%);
  min-height: min(760px, 90vh);
  gap: 18px;
}

.chapter-back {
  justify-self: start;
  border: 0;
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  font-weight: 900;
}

.chapter-layout {
  display: grid;
  grid-template-columns: minmax(200px, 0.34fr) minmax(0, 1fr);
  gap: 18px;
}

.chapter-list,
.chapter-detail {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
}

.chapter-list {
  display: grid;
  align-content: start;
  gap: 10px;
}

.chapter-list button {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-text);
  cursor: pointer;
  font-weight: 800;
  padding: 10px;
  text-align: left;
}

.chapter-list button.active {
  border-color: var(--color-primary-bright);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.chapter-detail {
  min-height: 520px;
}

.chapter-detail p {
  white-space: pre-line;
}

.confirm-button {
  align-self: end;
  justify-self: end;
  min-width: 190px;
}

@media (max-width: 1000px) {
  .create-layout {
    grid-template-columns: 1fr;
    row-gap: 18px;
  }

  .route-panel {
    position: static;
  }
}

@media (max-width: 700px) {
  .create-header,
  .field-grid,
  .field-grid.two,
  .chapter-layout {
    grid-template-columns: 1fr;
  }

  .section-heading.split,
  .route-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .chapter-card {
    min-height: 82vh;
  }
}

/* Taste pass: compact production workflow, with dividers replacing nested cards. */
.create-shell {
  gap: 14px;
}

.create-header {
  min-height: 58px;
  align-items: center;
  border-bottom: 1px solid rgba(161, 211, 202, 0.55);
  padding-bottom: 12px;
}

.create-header h1 {
  font-size: clamp(26px, 3vw, 40px);
  letter-spacing: 0;
}

.back-link {
  width: 36px;
  height: 36px;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.7);
}

.create-layout {
  grid-template-columns: minmax(360px, var(--form-column-percent)) 10px minmax(320px, 1fr);
  gap: 0;
}

.form-stack {
  border-right: 1px solid rgba(161, 211, 202, 0.58);
  padding-right: 18px;
}

.form-panel {
  border: 0;
  border-bottom: 1px solid rgba(161, 211, 202, 0.5);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 18px 0;
}

.form-panel:first-child {
  padding-top: 0;
}

.section-heading h2,
.route-heading h2 {
  font-size: 20px;
}

.upload-zone,
.empty-route,
.chunk-list article,
.chapter-list,
.chapter-detail {
  border-radius: 0;
  box-shadow: none;
}

.upload-zone {
  background: rgba(236, 253, 245, 0.58);
}

.route-panel {
  top: 70px;
  border: 0;
  border-radius: 0;
  background: rgba(248, 253, 251, 0.86);
  box-shadow: none;
  padding: 0 0 0 18px;
}

.route-textarea {
  min-height: 260px;
}

.route-list {
  border-top: 1px solid rgba(161, 211, 202, 0.5);
  padding-top: 12px;
}

.modal-backdrop {
  background: rgba(15, 35, 32, 0.48);
  backdrop-filter: blur(10px);
}

.modal-card {
  border-radius: 10px;
  box-shadow: 0 28px 90px rgba(15, 35, 32, 0.28);
}

.chapter-card {
  width: min(1180px, 100%);
  min-height: min(820px, 92vh);
}

.chapter-layout {
  grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
}

.chapter-list,
.chapter-detail {
  background: rgba(248, 253, 251, 0.72);
}

.chapter-list button {
  border: 0;
  border-left: 3px solid transparent;
  border-radius: 0;
  background: transparent;
}

.chapter-list button.active {
  border-color: #14b8a6;
}

.chapter-detail {
  min-height: 600px;
}

@media (max-width: 1000px) {
  .create-layout {
    gap: 18px;
  }

  .form-stack {
    border-right: 0;
    padding-right: 0;
  }

  .route-panel {
    padding-left: 0;
  }
}

/* Primer redesign pass: create-space is a focused setup workspace, not stacked cards. */
.create-shell {
  min-height: calc(100dvh - 56px);
  gap: 0;
}

.create-header {
  border-bottom: 1px solid var(--color-border);
  padding: 18px 0 16px;
}

.create-header h1 {
  font-size: 20px;
  line-height: 1.25;
}

.create-header p {
  max-width: 760px;
}

.back-link {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  font-size: 18px;
}

.create-layout {
  grid-template-columns: minmax(360px, var(--form-column-percent)) 10px minmax(320px, 1fr);
  column-gap: 18px;
}

.form-stack {
  border-right: 0;
  gap: 0;
  padding: 18px 0;
}

.form-panel {
  border: 0;
  border-bottom: 1px solid var(--color-border);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 0 0 18px;
}

.form-panel + .form-panel {
  padding-top: 18px;
}

.section-heading {
  min-height: auto;
}

.step-inline-heading {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.step-inline-heading .eyebrow {
  margin-bottom: 0;
}

.section-heading h2,
.route-heading h2 {
  font-size: 15px;
}

.field-grid {
  gap: 10px;
}

.upload-zone,
.empty-route {
  border: 1px dashed var(--color-border);
  border-radius: 6px;
  background: var(--color-page);
}

.upload-zone:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.route-panel {
  position: sticky;
  top: 72px;
  align-self: start;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 18px 0;
}

.route-heading {
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 12px;
}

.route-textarea {
  min-height: 300px;
  margin-top: 12px;
}

.route-list {
  border-top: 1px solid var(--color-border);
  gap: 0;
  padding-top: 0;
}

.route-list li {
  border-bottom: 1px solid var(--color-border);
  border-radius: 0;
  padding: 10px 0;
}

.detail-button {
  margin-top: 14px;
  width: 100%;
}

.modal-backdrop {
  background: rgba(31, 35, 40, 0.36);
  backdrop-filter: blur(6px);
}

.modal-card {
  border-color: var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  box-shadow: var(--shadow-floating);
}

.modal-close,
.chapter-back {
  border-radius: 6px;
}

.chapter-card {
  width: min(1180px, calc(100vw - 36px));
  min-height: min(800px, calc(100dvh - 48px));
}

.chapter-layout {
  grid-template-columns: minmax(220px, 290px) minmax(0, 1fr);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
}

.chapter-list,
.chapter-detail {
  border: 0;
  border-radius: 0;
  background: var(--color-surface);
}

.chapter-list {
  border-right: 1px solid var(--color-border);
}

.chapter-list button {
  border-bottom: 1px solid var(--color-border);
  border-left: 3px solid transparent;
}

.chapter-list button.active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

@media (max-width: 1000px) {
  .create-layout {
    grid-template-columns: 1fr;
  }

  .layout-resizer {
    display: none;
  }

  .form-stack {
    border-right: 0;
    padding-right: 0;
  }

  .route-panel {
    position: static;
    padding-left: 0;
  }
}
</style>
