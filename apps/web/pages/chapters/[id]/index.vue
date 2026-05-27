<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

interface ChapterStudyChapter {
  id: string
  study_space_id: string
  learning_route_id: string
  order_index: number
  title: string
  goal: string
  summary: string
  estimated_days: number
  status: string
  source_chunk_refs: Array<Record<string, unknown>>
}

interface ChapterStudyRoute {
  id: string
  study_space_id: string
  version: number
  status: string
  title: string
}

interface ChapterStudySpace {
  id: string
  name: string
}

interface ChapterEvidence {
  source_id: string
  chunk_id: string
  chunk_index: number
  source_filename: string
  text: string
  citation: Record<string, unknown>
}

interface ChapterStudyDetail {
  chapter: ChapterStudyChapter
  route: ChapterStudyRoute
  study_space: ChapterStudySpace
  evidence: ChapterEvidence[]
  next_chapter_id: string | null
}

interface MentorCitation {
  chunk_id: string
  source_id: string
  source_filename: string
  chunk_index: number
  text: string
}

interface MentorAnswer {
  question: string
  answer: string
  citations: MentorCitation[]
}

const DEV_AUTH_HEADERS = {
  'X-User-Id': '00000000-0000-0000-0000-000000000002',
  'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
}

const route = useRoute()
const config = useRuntimeConfig()
const chapterId = computed(() => String(route.params.id))

const detail = ref<ChapterStudyDetail | null>(null)
const loading = ref(false)
const completing = ref(false)
const askingMentor = ref(false)
const errorMessage = ref('')
const mentorErrorMessage = ref('')
const mentorQuestion = ref('')
const mentorAnswers = ref<MentorAnswer[]>([])

const chapter = computed(() => detail.value?.chapter ?? null)
const evidence = computed(() => detail.value?.evidence ?? [])
const isCompleted = computed(() => chapter.value?.status === 'completed')

function protectedHeaders() {
  return DEV_AUTH_HEADERS
}

function appendBackendMessage(base: string, error: unknown) {
  if (error instanceof Error && error.message) return `${base} ${error.message}`
  return base
}

function citationSummary(citation: Record<string, unknown>) {
  const page = citation.page_number ?? citation.page
  if (page) return `Page ${page}`
  return Object.keys(citation).length ? JSON.stringify(citation) : 'No citation metadata'
}

async function loadChapter() {
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await $fetch<ChapterStudyDetail>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}`,
      { headers: protectedHeaders() }
    )
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to load chapter.', error)
  } finally {
    loading.value = false
  }
}

async function completeCurrentChapter() {
  if (!chapter.value || isCompleted.value) return
  completing.value = true
  errorMessage.value = ''
  try {
    detail.value = await $fetch<ChapterStudyDetail>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/complete`,
      {
        method: 'POST',
        headers: protectedHeaders()
      }
    )
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to complete chapter.', error)
  } finally {
    completing.value = false
  }
}

async function askMentor() {
  const question = mentorQuestion.value.trim()
  if (!chapter.value || !question) return

  askingMentor.value = true
  mentorErrorMessage.value = ''
  try {
    const answer = await $fetch<MentorAnswer>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/mentor/questions`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { question }
      }
    )
    mentorAnswers.value = [...mentorAnswers.value, answer]
    mentorQuestion.value = ''
  } catch (error) {
    mentorErrorMessage.value = appendBackendMessage('Failed to ask mentor.', error)
  } finally {
    askingMentor.value = false
  }
}

onMounted(() => {
  loadChapter()
})
</script>

<template>
  <section class="chapter-study page-enter">
    <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>
    <p v-if="loading" class="muted">Loading chapter...</p>

    <template v-if="detail && chapter">
      <div class="topbar chapter-heading">
        <div>
          <p class="eyebrow">Chapter {{ chapter.order_index }} / {{ detail.study_space.name }}</p>
          <h1>{{ chapter.title }}</h1>
          <p>{{ detail.route.title }}</p>
        </div>
        <NuxtLink class="secondary-button back-link" :to="`/spaces/${chapter.study_space_id}`">
          Back to space
        </NuxtLink>
      </div>

      <section class="card chapter-summary">
        <div class="summary-grid">
          <div>
            <p class="eyebrow">Goal</p>
            <h2>{{ chapter.goal }}</h2>
            <p>{{ chapter.summary }}</p>
          </div>
          <dl class="chapter-meta">
            <div>
              <dt>Status</dt>
              <dd><span class="status-badge">{{ chapter.status }}</span></dd>
            </div>
            <div>
              <dt>Estimated</dt>
              <dd>{{ chapter.estimated_days }} days</dd>
            </div>
          </dl>
        </div>
      </section>

      <div class="study-grid">
        <section class="card evidence-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Source evidence</p>
              <h2>Grounding material</h2>
            </div>
            <span v-if="evidence.length" class="chunk-count">{{ evidence.length }} excerpts</span>
          </div>

          <div v-if="evidence.length" class="evidence-list">
            <article v-for="item in evidence" :key="item.chunk_id" class="evidence-card">
              <div class="evidence-header">
                <h3>{{ item.source_filename }}</h3>
                <span>Chunk #{{ item.chunk_index }}</span>
              </div>
              <p>{{ item.text }}</p>
              <small>{{ citationSummary(item.citation) }}</small>
            </article>
          </div>
          <p v-else class="empty-state">No source evidence is linked to this chapter yet.</p>
        </section>

        <aside class="card mentor-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">AI Mentor</p>
              <h2>Chapter help</h2>
            </div>
          </div>

          <div class="mentor-thread" aria-live="polite">
            <article v-if="!mentorAnswers.length" class="mentor-empty">
              <p>Ask a question about this chapter.</p>
            </article>

            <article v-for="answer in mentorAnswers" :key="answer.question" class="mentor-exchange">
              <p class="mentor-question">{{ answer.question }}</p>
              <div class="mentor-answer">
                <p>{{ answer.answer }}</p>
                <div v-if="answer.citations.length" class="mentor-citations">
                  <p class="eyebrow">Citations</p>
                  <article
                    v-for="citation in answer.citations"
                    :key="citation.chunk_id"
                    class="mentor-citation"
                  >
                    <div>
                      <strong>{{ citation.source_filename }}</strong>
                      <span>Chunk #{{ citation.chunk_index }}</span>
                    </div>
                    <p>{{ citation.text }}</p>
                  </article>
                </div>
              </div>
            </article>
          </div>

          <p v-if="mentorErrorMessage" class="error-alert">{{ mentorErrorMessage }}</p>
          <form class="mentor-form" @submit.prevent="askMentor">
            <textarea
              v-model="mentorQuestion"
              data-testid="mentor-question"
              placeholder="Ask about this chapter"
              :disabled="askingMentor"
            />
            <button
              data-testid="ask-mentor"
              class="secondary-button"
              type="submit"
              :disabled="askingMentor"
            >
              {{ askingMentor ? 'Asking...' : 'Ask mentor' }}
            </button>
          </form>
        </aside>
      </div>

      <section class="card chapter-actions">
        <button
          data-testid="complete-chapter"
          class="primary-button"
          type="button"
          :disabled="isCompleted || completing"
          @click="completeCurrentChapter"
        >
          {{ isCompleted ? 'Completed' : completing ? 'Completing...' : 'Mark complete' }}
        </button>
        <NuxtLink
          v-if="detail.next_chapter_id"
          class="secondary-button next-link"
          :to="`/chapters/${detail.next_chapter_id}`"
        >
          Next chapter
        </NuxtLink>
      </section>
    </template>
  </section>
</template>

<style scoped>
.chapter-study {
  display: grid;
  gap: 18px;
}

.chapter-heading,
.summary-grid,
.study-grid,
.chapter-actions,
.section-heading,
.evidence-header {
  display: flex;
  gap: 14px;
}

.chapter-heading,
.section-heading,
.evidence-header {
  align-items: center;
  justify-content: space-between;
}

.summary-grid {
  align-items: start;
  justify-content: space-between;
}

.study-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
  align-items: start;
}

.chapter-summary,
.evidence-panel,
.mentor-panel {
  display: grid;
  gap: 16px;
}

.chapter-meta {
  display: grid;
  gap: 12px;
  min-width: 160px;
}

.chapter-meta dt {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.chapter-meta dd {
  margin: 4px 0 0;
}

.evidence-list {
  display: grid;
  gap: 12px;
}

.evidence-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  padding: 14px;
}

.evidence-card p {
  color: var(--color-text);
  white-space: pre-wrap;
}

.evidence-card small,
.muted,
.chapter-heading p {
  color: var(--color-muted);
}

.chunk-count {
  border-radius: 999px;
  padding: 5px 8px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
}

.mentor-panel {
  position: sticky;
  top: 18px;
}

.mentor-thread {
  display: grid;
  gap: 14px;
  max-height: 520px;
  overflow: auto;
  padding-right: 2px;
}

.mentor-empty,
.mentor-answer,
.mentor-citation {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
}

.mentor-empty {
  padding: 14px;
  color: var(--color-muted);
}

.mentor-exchange {
  display: grid;
  gap: 10px;
}

.mentor-question {
  justify-self: end;
  max-width: 86%;
  border: 1px solid rgba(20, 184, 166, 0.28);
  border-radius: 8px;
  background: var(--color-primary-soft);
  color: var(--color-text);
  padding: 10px 12px;
}

.mentor-answer {
  display: grid;
  gap: 12px;
  padding: 14px;
  box-shadow: 0 14px 36px rgba(15, 118, 110, 0.08);
}

.mentor-answer > p {
  color: var(--color-text);
  white-space: pre-wrap;
}

.mentor-citations {
  display: grid;
  gap: 8px;
}

.mentor-citation {
  display: grid;
  gap: 8px;
  padding: 10px;
}

.mentor-citation div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mentor-citation span,
.mentor-citation p {
  color: var(--color-muted);
}

.mentor-form {
  display: grid;
  gap: 10px;
}

.mentor-form textarea {
  min-height: 120px;
  resize: vertical;
}

.back-link,
.next-link {
  text-decoration: none;
}

@media (max-width: 960px) {
  .study-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .chapter-heading,
  .chapter-actions,
  .section-heading,
  .evidence-header {
    align-items: stretch;
    flex-direction: column;
  }

  .mentor-panel {
    position: static;
  }
}
</style>
