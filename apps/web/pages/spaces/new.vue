<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

type RouteChapter = {
  order: number
  title: string
  description: string
  estimated_days: number
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
  embeddingModel: 'text-embedding-3-small'
})

const DEV_AUTH_HEADERS = {
  'X-User-Id': '00000000-0000-0000-0000-000000000002',
  'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
}

const routeOutline = ref<RouteChapter[]>([])
const routeDraftText = ref('')
const showChunkModal = ref(false)
const showChapterModal = ref(false)
const generatingDetails = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

const materialChunks = [
  {
    title: 'Chunk 01',
    body: '学习目标、基础背景、材料范围会在创建后进入 RAG 管线。'
  },
  {
    title: 'Chunk 02',
    body: '章节草稿将用于生成学习路径、练习和后续检索上下文。'
  },
  {
    title: 'Embedded sample',
    body: 'Embedding model 可选配置保留在创建页，用于后续材料索引体验。'
  }
]

const selectedChapter = ref(0)

const chapterDetails = ref([
  {
    title: '目标拆解',
    detail: '明确学习空间的边界、先修知识、验收标准和每天的学习节奏。'
  },
  {
    title: '概念地图',
    detail: '把上传材料中的核心概念整理成章节结构，并标记概念之间的依赖关系。'
  },
  {
    title: '练习巩固',
    detail: '围绕章节重点生成复习提示、测验题和错题回看任务。'
  }
])

const selectedChapterDetail = computed(() => {
  return chapterDetails.value[selectedChapter.value] ?? chapterDetails.value[0] ?? {
    title: '章节详情',
    detail: '暂无章节详情。'
  }
})

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
  routeDraftText.value = routeOutline.value
    .map((chapter) => `${chapter.order}. ${chapter.title} (${chapter.estimated_days} days)\n${chapter.description}`)
    .join('\n\n')
}

function generateChapterDetails() {
  generatingDetails.value = true
  showChapterModal.value = false
  window.setTimeout(() => {
    if (routeOutline.value.length) {
      chapterDetails.value = routeOutline.value.map((chapter) => ({
        title: chapter.title,
        detail: `${chapter.description}\n\n建议学习时长：${chapter.estimated_days} 天。先阅读材料摘要，再完成章节练习，最后记录疑问用于下一轮复习。`
      }))
    }
    selectedChapter.value = 0
    generatingDetails.value = false
    showChapterModal.value = true
  }, 10)
}

async function createSpace() {
  const config = useRuntimeConfig()
  const router = useRouter()
  submitting.value = true
  errorMessage.value = ''
  try {
    const created = await $fetch<{ id: string }>(`${config.public.apiBaseUrl}/study-spaces`, {
      method: 'POST',
      headers: DEV_AUTH_HEADERS,
      body: {
        ...form
      }
    })
    await router.push(`/spaces/${created.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to create study space'
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
          <h1>创建学习空间</h1>
          <p>配置目标、模型和材料入口，再生成可编辑学习路线。</p>
        </div>
      </header>

      <form class="create-layout" @submit.prevent="createSpace">
        <main class="form-stack">
          <section class="card form-panel">
            <div class="section-heading">
              <p class="eyebrow">Goal</p>
              <h2>学习空间名字</h2>
            </div>

            <label class="form-field">
              学习空间名字
              <input v-model="form.name" name="space-name" class="input" required maxlength="160">
            </label>

            <label class="form-field">
              学习主题 / Goal
              <textarea v-model="form.goal" name="learning-goal" class="textarea" required rows="5" />
            </label>

            <div class="field-grid">
              <label class="form-field">
                Level
                <select v-model="form.level" class="select">
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </label>

              <label class="form-field">
                Intensity
                <select v-model="form.intensity" class="select">
                  <option value="light">Light</option>
                  <option value="normal">Normal</option>
                  <option value="intensive">Intensive</option>
                </select>
              </label>

              <label class="form-field">
                Target days
                <input v-model.number="form.target_days" class="input" type="number" min="1" max="365">
              </label>
            </div>
          </section>

          <section class="card form-panel">
            <div class="section-heading">
              <p class="eyebrow">Model</p>
              <h2>默认模型选择 / 输入</h2>
            </div>

            <div class="field-grid two">
              <label class="form-field">
                默认模型
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
            </div>
          </section>

          <section class="card form-panel">
            <div class="section-heading split">
              <div>
                <p class="eyebrow">Materials</p>
                <h2>上传材料 / RAG</h2>
              </div>
              <button data-testid="open-chunk-modal" class="secondary-button" type="button" @click="showChunkModal = true">
                查看 chunks
              </button>
            </div>

            <label class="upload-zone">
              <span>Drop files here or click to upload</span>
              <small>PDF, markdown, notes, and exported course material</small>
              <input type="file" multiple>
            </label>

            <label class="form-field">
              Embedding model
              <input v-model="modelSettings.embeddingModel" class="input" placeholder="text-embedding-3-small">
            </label>
          </section>
        </main>

        <aside class="route-panel">
          <div class="route-heading">
            <div>
              <p class="eyebrow">Route outline</p>
              <h2>Draft route</h2>
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
            <p>Generate a route draft after filling in the learning goal.</p>
          </div>

          <ol v-if="routeOutline.length" class="route-list">
            <li v-for="chapter in routeOutline" :key="chapter.order">
              <strong>{{ chapter.title }}</strong>
              <small>{{ chapter.estimated_days }} days</small>
            </li>
          </ol>

          <button
            data-testid="generate-chapter-details"
            class="primary-button detail-button"
            type="button"
            :disabled="generatingDetails"
            @click="generateChapterDetails"
          >
            {{ generatingDetails ? '正在生成中，请稍等' : '生成章节学习详情' }}
          </button>

          <p v-if="generatingDetails" class="loading-copy">正在生成中，请稍等</p>
          <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>

          <div class="action-row">
            <button class="primary-button" type="submit" :disabled="submitting">
              {{ submitting ? 'Creating...' : 'Create Space' }}
            </button>
          </div>
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
        <h2 id="chunk-title">Chunk / embedded 内容</h2>
        <div class="chunk-list">
          <article v-for="chunk in materialChunks" :key="chunk.title">
            <strong>{{ chunk.title }}</strong>
            <p>{{ chunk.body }}</p>
          </article>
        </div>
      </section>
    </div>

    <div v-if="showChapterModal" data-testid="chapter-modal" class="modal-backdrop">
      <section class="modal-card chapter-card" role="dialog" aria-modal="true" aria-labelledby="chapter-title">
        <button class="chapter-back" type="button" @click="showChapterModal = false">
          <span aria-hidden="true">←</span>
          Close
        </button>

        <div class="chapter-layout">
          <aside class="chapter-list">
            <p class="eyebrow">章节列表</p>
            <button
              v-for="(chapter, index) in chapterDetails"
              :key="chapter.title"
              type="button"
              :class="{ active: selectedChapter === index }"
              @click="selectedChapter = index"
            >
              {{ chapter.title }}
            </button>
          </aside>

          <article class="chapter-detail">
            <p class="eyebrow">章节详情</p>
            <h2 id="chapter-title">{{ selectedChapterDetail.title }}</h2>
            <p>{{ selectedChapterDetail.detail }}</p>
          </article>
        </div>

        <button
          data-testid="confirm-chapter-details"
          class="primary-button confirm-button"
          type="button"
          :disabled="submitting"
          @click="createSpace"
        >
          {{ submitting ? 'Creating...' : '确认' }}
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
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.42fr);
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
.route-heading,
.action-row {
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.upload-zone {
  display: grid;
  gap: 5px;
  border: 1px dashed var(--color-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--color-primary-soft) 38%, transparent);
  cursor: pointer;
  padding: 24px;
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

.route-panel {
  position: sticky;
  top: 18px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: var(--shadow-soft);
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
  width: min(980px, 100%);
  min-height: min(680px, 88vh);
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
  grid-template-columns: minmax(180px, 0.34fr) minmax(0, 1fr);
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
  min-height: 430px;
}

.chapter-detail p {
  white-space: pre-line;
}

.confirm-button {
  align-self: end;
  justify-self: end;
  min-width: 132px;
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
  .route-heading,
  .action-row {
    align-items: stretch;
    flex-direction: column;
  }

  .chapter-card {
    min-height: 82vh;
  }
}
</style>
