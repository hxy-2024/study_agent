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

interface MentorSession {
  id: string
  chapter_id: string
  title?: string
}

interface MentorMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
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
const loadingMentor = ref(false)
const errorMessage = ref('')
const mentorErrorMessage = ref('')
const mentorQuestion = ref('')
const mentorSession = ref<MentorSession | null>(null)
const mentorMessages = ref<MentorMessage[]>([])

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

function normalizeSessions(response: MentorSession[] | { sessions?: MentorSession[] }) {
  return Array.isArray(response) ? response : response.sessions ?? []
}

function normalizeMessages(response: MentorMessage[] | { messages?: MentorMessage[] }) {
  return Array.isArray(response) ? response : response.messages ?? []
}

function localUserMessage(sessionId: string, content: string): MentorMessage {
  return {
    id: `local-user-${Date.now()}`,
    session_id: sessionId,
    role: 'user',
    content,
    citations: []
  }
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

async function loadMentorMessages(sessionId: string) {
  const response = await $fetch<MentorMessage[] | { messages?: MentorMessage[] }>(
    `${config.public.apiBaseUrl}/sessions/${sessionId}/messages`,
    { headers: protectedHeaders() }
  )
  mentorMessages.value = normalizeMessages(response)
}

async function loadMentorSession() {
  loadingMentor.value = true
  mentorErrorMessage.value = ''
  try {
    const response = await $fetch<MentorSession[] | { sessions?: MentorSession[] }>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/sessions`,
      { headers: protectedHeaders() }
    )
    mentorSession.value = normalizeSessions(response)[0] ?? null
    if (mentorSession.value) {
      await loadMentorMessages(mentorSession.value.id)
    } else {
      mentorMessages.value = []
    }
  } catch (error) {
    mentorErrorMessage.value = appendBackendMessage('Failed to load mentor session.', error)
  } finally {
    loadingMentor.value = false
  }
}

async function ensureMentorSession() {
  if (mentorSession.value) return mentorSession.value

  const session = await $fetch<MentorSession>(
    `${config.public.apiBaseUrl}/chapters/${chapterId.value}/sessions`,
    {
      method: 'POST',
      headers: protectedHeaders()
    }
  )
  mentorSession.value = session
  return session
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
    const session = await ensureMentorSession()
    const answer = await $fetch<MentorMessage>(
      `${config.public.apiBaseUrl}/sessions/${session.id}/messages`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { content: question }
      }
    )
    mentorMessages.value = [...mentorMessages.value, localUserMessage(session.id, question), answer]
    mentorQuestion.value = ''
  } catch (error) {
    mentorErrorMessage.value = appendBackendMessage('Failed to ask mentor.', error)
  } finally {
    askingMentor.value = false
  }
}

onMounted(() => {
  loadChapter()
  loadMentorSession()
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
            <article v-if="loadingMentor" class="mentor-empty">
              <p>Loading mentor session...</p>
            </article>
            <article v-else-if="!mentorMessages.length" class="mentor-empty">
              <p>Ask a question about this chapter.</p>
            </article>

            <article v-for="message in mentorMessages" :key="message.id" class="mentor-exchange">
              <p v-if="message.role === 'user'" class="mentor-question">{{ message.content }}</p>
              <div v-else class="mentor-answer">
                <p>{{ message.content }}</p>
                <div v-if="message.citations?.length" class="mentor-citations">
                  <p class="eyebrow">Citations</p>
                  <article
                    v-for="citation in message.citations"
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
