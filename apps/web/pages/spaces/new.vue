<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

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

const form = reactive({
  name: '',
  goal: '',
  level: 'beginner',
  intensity: 'normal',
  target_days: 30
})

const modelSettings = reactive({
  defaultModel: 'gpt-4.1-mini',
  customModel: '',
  embeddingModel: ''
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
const submitting = ref(false)
const errorMessage = ref('')
const selectedChapter = ref(0)

const chapterDetails = ref<RouteChapter[]>([
  {
    order: 1,
    title: 'Goal breakdown',
    description: 'Clarify scope, prerequisites, completion criteria, and the daily learning cadence.',
    estimated_days: 2
  },
  {
    order: 2,
    title: 'Concept map',
    description: 'Turn uploaded material into a chapter structure and mark concept dependencies.',
    estimated_days: 4
  },
  {
    order: 3,
    title: 'Practice reinforcement',
    description: 'Generate review prompts, quizzes, and weak-point follow-up tasks around chapter goals.',
    estimated_days: 2
  }
])

const selectedChapterDetail = computed(() => {
  return chapterDetails.value[selectedChapter.value] ?? chapterDetails.value[0] ?? {
    order: 1,
    title: 'Chapter detail',
    description: 'No chapter detail has been generated yet.',
    estimated_days: 1
  }
})

const canRunRag = computed(() => {
  return Boolean(form.name.trim() && form.goal.trim() && material.content.trim())
})

function syncRouteDraftText(chapters: RouteChapter[]) {
  routeDraftText.value = chapters
    .map((chapter) => {
      return `${chapter.order}. ${chapter.title} (${chapter.estimated_days} days)\n${chapter.description}`
    })
    .join('\n\n')
}

function renderDraftRoute() {
  const first = Math.max(1, Math.floor(form.target_days / 4))
  const second = Math.max(1, Math.floor(form.target_days / 2))
  const third = Math.max(1, form.target_days - first - second)
  routeOutline.value = [
    {
      order: 1,
      title: 'Clarify the learning goal',
      description: `Define the scope, existing foundation, and completion criteria for ${form.goal || 'this study goal'}.`,
      estimated_days: first
    },
    {
      order: 2,
      title: 'Build the core knowledge map',
      description: 'Break source material into key concepts and connect them into a usable learning structure.',
      estimated_days: second
    },
    {
      order: 3,
      title: 'Review, test, and reinforce',
      description: 'Use quizzes, weak-point review, and spaced practice to check mastery.',
      estimated_days: third
    }
  ]
  syncRouteDraftText(routeOutline.value)
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

async function runRag() {
  if (!canRunRag.value) {
    errorMessage.value = 'Fill in the space name, learning goal, and material before running ingestion.'
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
      headers: DEV_AUTH_HEADERS
    })
    const chunks = await $fetch<SourceChunkList>(`${config.public.apiBaseUrl}/sources/${sourceId.value}/chunks`, {
      headers: DEV_AUTH_HEADERS
    })
    materialChunks.value = chunks.chunks
    await createRouteDraft(studySpaceId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'RAG processing failed'
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
        renderDraftRoute()
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
      throw new Error('Chapters are not ready yet. Run RAG or generate a route first.')
    }
    await router.push(`/chapters/${firstChapterId}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to enter chapter study'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="create-space page-enter">
    <div class="create-shell">
      <header class="create-header">
        <NuxtLink data-testid="back-home" class="back-link" to="/" aria-label="Back to dashboard">
          <span aria-hidden="true">←</span>
        </NuxtLink>
        <div>
          <p class="eyebrow">New learning space</p>
          <h1>Create learning space</h1>
          <p>Set the goal, upload material, run ingestion, review the AI route, and enter chapter study.</p>
        </div>
      </header>

      <form class="create-layout" @submit.prevent="generateChapterDetails">
        <main class="form-stack">
          <section class="card form-panel">
            <div class="section-heading">
              <p class="eyebrow">Step 1</p>
              <h2>Space and learning goal</h2>
            </div>

            <label class="form-field">
              Space name
              <input v-model="form.name" name="space-name" class="input" required maxlength="160">
            </label>

            <label class="form-field">
              Learning goal
              <textarea v-model="form.goal" name="learning-goal" class="textarea" required rows="4" />
            </label>

            <div class="field-grid">
              <label class="form-field">
                Default model
                <select v-model="modelSettings.defaultModel" class="select">
                  <option value="gpt-4.1-mini">gpt-4.1-mini</option>
                  <option value="gpt-4.1">gpt-4.1</option>
                  <option value="custom">Custom model</option>
                </select>
              </label>

              <label class="form-field">
                Model input
                <input v-model="modelSettings.customModel" class="input" placeholder="Optional custom model id">
              </label>

              <label class="form-field">
                Target days
                <input v-model.number="form.target_days" class="input" type="number" min="1" max="365">
              </label>
            </div>
          </section>

          <section class="card form-panel">
            <div class="section-heading split">
              <div>
                <p class="eyebrow">Step 2</p>
                <h2>Material and RAG ingestion</h2>
              </div>
              <button
                data-testid="open-chunk-modal"
                class="secondary-button"
                type="button"
                :disabled="!materialChunks.length"
                @click="showChunkModal = true"
              >
                View chunks
              </button>
            </div>

            <label class="upload-zone">
              <span>Upload Markdown or text</span>
              <small>{{ material.filename }}</small>
              <input type="file" accept=".md,.txt,text/markdown,text/plain" @change="handleMaterialFile">
            </label>

            <label class="form-field">
              Or paste material
              <textarea v-model="material.content" class="textarea" rows="7" placeholder="Paste course notes, Markdown, or article text..." />
            </label>

            <div class="field-grid two">
              <label class="form-field">
                Embedding model
                <input v-model="modelSettings.embeddingModel" class="input" placeholder="Optional; empty uses default chunk embeddings">
              </label>
              <button
                data-testid="run-rag"
                class="primary-button rag-button"
                type="button"
                :disabled="runningRag || !canRunRag"
                @click="runRag"
              >
                {{ runningRag ? 'Running ingestion...' : 'Run ingestion' }}
              </button>
            </div>
          </section>
        </main>

        <aside class="route-panel">
          <div class="route-heading">
            <div>
              <p class="eyebrow">Step 3</p>
              <h2>Learning route outline</h2>
            </div>
            <button class="secondary-button ai-render" type="button" @click="renderDraftRoute">AI Render</button>
          </div>

          <textarea
            v-if="routeDraftText"
            v-model="routeDraftText"
            class="textarea route-textarea"
            aria-label="Editable route outline"
          />
          <div v-else class="empty-route">
            <p>After ingestion, the AI-generated route appears here. You can also render a draft first.</p>
          </div>

          <ol v-if="routeOutline.length" class="route-list">
            <li v-for="chapter in routeOutline" :key="`${chapter.order}-${chapter.title}`">
              <strong>{{ chapter.title }}</strong>
              <small>{{ chapter.estimated_days }} days</small>
            </li>
          </ol>

          <button
            data-testid="generate-chapter-details"
            class="primary-button detail-button"
            type="submit"
            :disabled="generatingDetails || runningRag"
          >
            {{ generatingDetails ? 'Generating, please wait...' : 'Generate chapter study details' }}
          </button>

          <p v-if="generatingDetails" class="loading-copy">Generating, please wait...</p>
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
          aria-label="Close chunk modal"
          @click="showChunkModal = false"
        >
          ×
        </button>
        <p class="eyebrow">RAG preview</p>
        <h2 id="chunk-title">Embedded chunks</h2>
        <div class="chunk-list">
          <article v-for="chunk in materialChunks" :key="chunk.id">
            <strong>Chunk {{ chunk.chunk_index + 1 }}</strong>
            <p>{{ chunk.text }}</p>
          </article>
        </div>
      </section>
    </div>

    <div v-if="showChapterModal" data-testid="chapter-modal" class="modal-backdrop">
      <section class="modal-card chapter-card" role="dialog" aria-modal="true" aria-labelledby="chapter-title">
        <button class="chapter-back" type="button" @click="showChapterModal = false">
          <span aria-hidden="true">←</span>
          Back
        </button>

        <div class="chapter-layout">
          <aside class="chapter-list">
            <p class="eyebrow">Chapters</p>
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
            <p class="eyebrow">Chapter detail</p>
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
          {{ submitting ? 'Entering...' : 'Confirm and enter chapter study' }}
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
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 0.42fr);
  gap: 18px;
  align-items: start;
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

.ai-render {
  background: linear-gradient(90deg, #e5484d, #2563eb);
  background-clip: text;
  color: transparent;
  font-weight: 900;
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
  grid-template-columns: minmax(0, 1fr) minmax(320px, 420px);
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
  grid-template-columns: minmax(0, 1fr) minmax(330px, 390px);
  gap: 0;
}

.form-stack {
  border-right: 1px solid var(--color-border);
  gap: 0;
  padding: 18px 22px 18px 0;
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
  padding: 18px 0 18px 22px;
}

.route-heading {
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 12px;
}

.ai-render {
  color: var(--color-primary);
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
