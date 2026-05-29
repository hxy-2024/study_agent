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

interface MasteryRecord {
  id: string
  chapter_id: string
  level: string
  score_percent: number
  weak_points: string[]
  last_quiz_submission_id?: string
  updated_at?: string
}

interface QuizSummary {
  id: string
  chapter_id: string
  question_count: number
}

interface ChapterAnnotation {
  id: string
  tenant_id: string
  user_id: string
  study_space_id: string
  chapter_id: string
  source_chunk_id: string | null
  kind: 'note' | 'highlight' | string
  content: string | null
  quote: string | null
  anchor: Record<string, unknown>
  created_at: string | null
  updated_at: string | null
}

const DEV_AUTH_HEADERS = {
  'X-User-Id': '00000000-0000-0000-0000-000000000002',
  'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
}

const route = useRoute()
const config = useRuntimeConfig()
const chapterId = computed(() => String(route.params.id))

const detail = ref<ChapterStudyDetail | null>(null)
const chapterNavigation = ref<ChapterStudyChapter[]>([])
const mentorSessions = ref<MentorSession[]>([])
const mentorSession = ref<MentorSession | null>(null)
const mentorMessages = ref<MentorMessage[]>([])
const annotations = ref<ChapterAnnotation[]>([])
const mastery = ref<MasteryRecord | null>(null)

const loading = ref(false)
const loadingMentor = ref(false)
const askingMentor = ref(false)
const savingNote = ref(false)
const completing = ref(false)
const generatingQuiz = ref(false)
const chapterRailCollapsed = ref(false)

const mentorQuestion = ref('')
const noteDraft = ref('')
const errorMessage = ref('')
const mentorErrorMessage = ref('')

const chapter = computed(() => detail.value?.chapter ?? null)
const notes = computed(() => annotations.value.filter(annotation => annotation.kind === 'note'))
const isCompleted = computed(() => chapter.value?.status === 'completed')
const canSaveNote = computed(() => noteDraft.value.trim().length > 0 && !savingNote.value)
const masteryLabel = computed(() => {
  if (!mastery.value) return 'not started'
  return `${mastery.value.level} ${mastery.value.score_percent}%`
})
const introMessage = computed(() => {
  if (!chapter.value) return ''
  return [
    `我是你的本章 AI Mentor。`,
    `这一章我们学习 **${chapter.value.title}**。`,
    `目标是：${chapter.value.goal}`,
    `你可以直接提问，也可以问我“下一步学什么”。我会按你的节奏继续讲解。`
  ].join('\n\n')
})

function protectedHeaders() {
  return DEV_AUTH_HEADERS
}

function appendBackendMessage(base: string, error: unknown) {
  if (error instanceof Error && error.message) return `${base} ${error.message}`
  return base
}

function normalizeSessions(response: MentorSession[] | { sessions?: MentorSession[] }) {
  return Array.isArray(response) ? response : response.sessions ?? []
}

function normalizeMessages(response: MentorMessage[] | { messages?: MentorMessage[] }) {
  return Array.isArray(response) ? response : response.messages ?? []
}

function normalizeAnnotations(response: { annotations?: ChapterAnnotation[] } | ChapterAnnotation[] | null | undefined) {
  return Array.isArray(response) ? response : response?.annotations ?? []
}

function normalizeChapters(response: { chapters?: ChapterStudyChapter[] } | ChapterStudyChapter[] | null | undefined) {
  return Array.isArray(response) ? response : response?.chapters ?? []
}

function preferredSessionId() {
  const sessionId = route.query?.session_id
  return typeof sessionId === 'string' ? sessionId : null
}

function isMasteryRecord(response: unknown): response is MasteryRecord {
  if (!response || typeof response !== 'object') return false
  const candidate = response as Partial<MasteryRecord>
  return typeof candidate.level === 'string' && typeof candidate.score_percent === 'number'
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

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function renderMarkdown(value: string) {
  const escaped = escapeHtml(value)
  return escaped
    .replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

async function loadChapter() {
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await $fetch<ChapterStudyDetail>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}`,
      { headers: protectedHeaders() }
    )
    await loadChapterNavigation(detail.value.chapter.study_space_id)
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to load chapter.', error)
  } finally {
    loading.value = false
  }
}

async function loadChapterNavigation(studySpaceId: string) {
  try {
    const response = await $fetch<{ chapters: ChapterStudyChapter[] }>(
      `${config.public.apiBaseUrl}/study-spaces/${studySpaceId}/chapters`,
      { headers: protectedHeaders() }
    )
    const chapters = normalizeChapters(response)
    chapterNavigation.value = chapters.length ? chapters : detail.value?.chapter ? [detail.value.chapter] : []
  } catch {
    chapterNavigation.value = detail.value?.chapter ? [detail.value.chapter] : []
  }
}

async function loadAnnotations() {
  try {
    const response = await $fetch<{ annotations: ChapterAnnotation[] }>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/annotations`,
      { headers: protectedHeaders() }
    )
    annotations.value = normalizeAnnotations(response)
  } catch {
    annotations.value = []
  }
}

async function createNote() {
  if (!canSaveNote.value) return
  savingNote.value = true
  errorMessage.value = ''
  try {
    const response = await $fetch<{ annotation: ChapterAnnotation }>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/annotations`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: {
          kind: 'note',
          content: noteDraft.value.trim()
        }
      }
    )
    annotations.value = [response.annotation, ...annotations.value]
    noteDraft.value = ''
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to save note.', error)
  } finally {
    savingNote.value = false
  }
}

async function deleteAnnotation(annotation: ChapterAnnotation) {
  errorMessage.value = ''
  try {
    await $fetch(`${config.public.apiBaseUrl}/chapter-annotations/${annotation.id}`, {
      method: 'DELETE',
      headers: protectedHeaders()
    })
    annotations.value = annotations.value.filter(item => item.id !== annotation.id)
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to delete annotation.', error)
  }
}

async function loadMastery() {
  try {
    const response = await $fetch<MasteryRecord>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/mastery`,
      { headers: protectedHeaders() }
    )
    mastery.value = isMasteryRecord(response) ? response : null
  } catch {
    mastery.value = null
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
    mentorSessions.value = normalizeSessions(response)
    const selectedSessionId = preferredSessionId()
    mentorSession.value = mentorSessions.value.find(session => session.id === selectedSessionId) ?? mentorSessions.value[0] ?? null
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
  return createNewSession()
}

async function createNewSession() {
  const session = await $fetch<MentorSession>(
    `${config.public.apiBaseUrl}/chapters/${chapterId.value}/sessions`,
    {
      method: 'POST',
      headers: protectedHeaders()
    }
  )
  mentorSession.value = session
  mentorSessions.value = [session, ...mentorSessions.value.filter(existing => existing.id !== session.id)]
  mentorMessages.value = []
  return session
}

async function askMentor() {
  const question = mentorQuestion.value.trim()
  if (!question) return

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

async function generateQuiz() {
  if (!chapter.value) return

  generatingQuiz.value = true
  errorMessage.value = ''
  try {
    const quiz = await $fetch<QuizSummary>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/quizzes/generate`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { question_count: 3 }
      }
    )
    await navigateTo(`/quizzes/${quiz.id}`)
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to generate quiz.', error)
  } finally {
    generatingQuiz.value = false
  }
}

onMounted(() => {
  loadChapter()
  loadMentorSession()
  loadMastery()
  loadAnnotations()
})
</script>

<template>
  <section class="chapter-workbench page-enter">
    <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>
    <p v-if="loading" class="muted">Loading chapter...</p>

    <template v-if="detail && chapter">
      <aside class="chapter-sidebar" :class="{ collapsed: chapterRailCollapsed }">
        <button class="rail-collapse" type="button" @click="chapterRailCollapsed = !chapterRailCollapsed">
          {{ chapterRailCollapsed ? '>>' : '<<' }}
        </button>

        <template v-if="!chapterRailCollapsed">
          <div class="rail-title">
            <span>{{ detail.study_space.name }}</span>
            <strong>Chapters</strong>
          </div>

          <nav class="chapter-list" aria-label="Chapter navigation">
            <NuxtLink
              v-for="item in chapterNavigation"
              :key="item.id"
              class="chapter-link"
              :class="{ active: item.id === chapter.id }"
              :to="`/chapters/${item.id}`"
            >
              <span>{{ item.order_index }}</span>
              <strong>{{ item.title }}</strong>
            </NuxtLink>
          </nav>
        </template>
      </aside>

      <main class="chat-workspace">
        <header class="chat-topbar">
          <div>
            <p>{{ detail.route.title }}</p>
            <h1>{{ chapter.title }}</h1>
          </div>
          <button
            data-testid="generate-quiz"
            class="quiz-button"
            type="button"
            :disabled="generatingQuiz"
            @click="generateQuiz"
          >
            {{ generatingQuiz ? 'Generating...' : 'Generate quiz' }}
          </button>
        </header>

        <section class="chat-thread" aria-live="polite">
          <article class="message-row assistant">
            <div class="message-avatar">AI</div>
            <div class="message-bubble">
              <div class="markdown-body" v-html="renderMarkdown(introMessage)" />
              <div class="message-actions">
                <button type="button">Fork checkpoint</button>
                <button type="button">Interrupt</button>
              </div>
            </div>
          </article>

          <article v-if="loadingMentor" class="message-row assistant">
            <div class="message-avatar">AI</div>
            <div class="message-bubble">Loading mentor session...</div>
          </article>

          <article
            v-for="message in mentorMessages"
            :key="message.id"
            class="message-row"
            :class="message.role === 'user' ? 'user' : 'assistant'"
          >
            <div class="message-avatar">{{ message.role === 'user' ? 'You' : 'AI' }}</div>
            <div class="message-bubble">
              <div class="markdown-body" v-html="renderMarkdown(message.content)" />
              <div v-if="message.citations?.length" class="citation-list">
                <article v-for="citation in message.citations" :key="citation.chunk_id" class="citation-card">
                  <strong>{{ citation.source_filename }}</strong>
                  <span>Chunk #{{ citation.chunk_index }}</span>
                  <p>{{ citation.text }}</p>
                </article>
              </div>
              <div v-if="message.role !== 'user'" class="message-actions">
                <button type="button">Fork checkpoint</button>
                <button type="button">Interrupt</button>
              </div>
            </div>
          </article>
        </section>

        <p v-if="mentorErrorMessage" class="error-alert">{{ mentorErrorMessage }}</p>
        <form class="mentor-form composer" @submit.prevent="askMentor">
          <div class="composer-tools">
            <button type="button">Attach</button>
            <select class="select" aria-label="Model">
              <option>Default model</option>
              <option>Fast tutor</option>
              <option>Deep tutor</option>
            </select>
            <select class="select" aria-label="Thinking strength">
              <option>Normal thinking</option>
              <option>Deep thinking</option>
            </select>
            <button type="button">Web search</button>
            <button type="button">MCP</button>
          </div>

          <div class="composer-input">
            <textarea
              v-model="mentorQuestion"
              data-testid="mentor-question"
              placeholder="Ask a question, request the next step, or paste a confusing excerpt"
              :disabled="askingMentor"
            />
            <button
              data-testid="ask-mentor"
              class="send-button"
              type="submit"
              :disabled="askingMentor"
              aria-label="Send message"
            >
              ↑
            </button>
          </div>
        </form>
      </main>

      <aside class="session-panel">
        <section class="session-section">
          <div class="panel-heading">
            <div>
              <p>Sessions</p>
              <h2>{{ mentorSession?.title ?? 'Default chapter session' }}</h2>
            </div>
            <button type="button" @click="createNewSession">New</button>
          </div>
          <div class="session-list">
            <button
              v-for="session in mentorSessions"
              :key="session.id"
              type="button"
              :class="{ active: mentorSession?.id === session.id }"
              @click="mentorSession = session; loadMentorMessages(session.id)"
            >
              {{ session.title ?? 'Chapter session' }}
            </button>
          </div>
        </section>

        <section class="session-section">
          <p>Progress</p>
          <div class="progress-strip">
            <span>{{ chapter.status }}</span>
          </div>
          <p>{{ chapter.estimated_days }} estimated days · Mastery: {{ masteryLabel }}</p>
          <button
            data-testid="complete-chapter"
            class="complete-button"
            type="button"
            :disabled="isCompleted || completing"
            @click="completeCurrentChapter"
          >
            {{ isCompleted ? 'Completed' : completing ? 'Completing...' : 'Mark complete' }}
          </button>
          <NuxtLink v-if="detail.next_chapter_id" class="next-link" :to="`/chapters/${detail.next_chapter_id}`">
            Next chapter
          </NuxtLink>
        </section>

        <section class="session-section">
          <p>Study notes</p>
          <h2>Personal notes</h2>
          <form class="note-form" @submit.prevent="createNote">
            <textarea
              v-model="noteDraft"
              data-testid="chapter-note-input"
              placeholder="Create a personal note"
              :disabled="savingNote"
            />
            <button
              data-testid="save-chapter-note"
              type="submit"
              :disabled="!canSaveNote"
            >
              {{ savingNote ? 'Saving...' : 'Save note' }}
            </button>
          </form>
          <div v-if="notes.length" class="note-list">
            <article v-for="note in notes" :key="note.id" class="note-card">
              <p>{{ note.content }}</p>
              <button type="button" @click="deleteAnnotation(note)">Delete</button>
            </article>
          </div>
          <p v-else class="empty-state">No notes yet.</p>
        </section>
      </aside>
    </template>
  </section>
</template>

<style scoped>
.chapter-workbench {
  width: min(100%, 1600px);
  min-height: calc(100vh - 58px);
  margin: -18px auto -24px;
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr) minmax(280px, 360px);
  background: #f5fbf9;
}

.chapter-sidebar,
.chat-workspace,
.session-panel {
  min-height: calc(100vh - 58px);
}

.chapter-sidebar {
  border-right: 1px solid var(--color-border);
  background:
    linear-gradient(180deg, rgba(236, 253, 245, 0.8), rgba(255, 255, 255, 0.92)),
    var(--color-surface);
  padding: 16px;
}

.chapter-sidebar.collapsed {
  width: 66px;
  min-width: 66px;
}

.rail-collapse {
  width: 42px;
  height: 38px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-primary);
  cursor: pointer;
  font-weight: 900;
}

.rail-title {
  display: grid;
  gap: 3px;
  margin: 18px 0;
}

.rail-title span,
.panel-heading p,
.session-section > p,
.chat-topbar p {
  color: var(--color-muted);
  font-size: 13px;
  margin: 0;
}

.rail-title strong {
  font-size: 20px;
}

.chapter-list {
  display: grid;
  gap: 8px;
}

.chapter-link {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--color-text);
  padding: 10px;
}

.chapter-link:hover,
.chapter-link.active {
  border-color: var(--color-primary-bright);
  background: #fff;
}

.chapter-link span {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 8px;
  background: var(--color-primary);
  color: #fff;
  font-weight: 900;
}

.chapter-link strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.chat-workspace {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  background: #fff;
}

.chat-topbar {
  min-height: 74px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px 18px;
}

.chat-topbar h1 {
  font-size: 22px;
  margin: 3px 0 0;
  overflow-wrap: anywhere;
}

.quiz-button,
.complete-button,
.next-link,
.panel-heading button,
.note-form button,
.session-list button,
.composer-tools button,
.message-actions button {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-primary);
  cursor: pointer;
  font-weight: 800;
  min-height: 36px;
  padding: 7px 11px;
}

.quiz-button {
  border-color: var(--color-primary-bright);
  background: var(--color-primary);
  color: #fff;
}

.chat-thread {
  display: grid;
  align-content: start;
  gap: 22px;
  overflow: auto;
  padding: 22px min(7vw, 72px);
}

.message-row {
  display: grid;
  grid-template-columns: 42px minmax(0, 820px);
  gap: 12px;
}

.message-row.user {
  grid-template-columns: minmax(0, 820px) 42px;
  justify-content: end;
}

.message-row.user .message-avatar {
  grid-column: 2;
  grid-row: 1;
}

.message-row.user .message-bubble {
  grid-column: 1;
  grid-row: 1;
  background: var(--color-primary-soft);
}

.message-avatar {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--color-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 900;
}

.message-bubble {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  padding: 15px;
}

.markdown-body {
  color: var(--color-text);
  font-size: 16px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 0 0 8px;
  line-height: 1.25;
}

.markdown-body :deep(code) {
  border-radius: 6px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  padding: 2px 5px;
}

.message-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.citation-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.citation-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #f8fffd;
  padding: 10px;
}

.citation-card span,
.citation-card p {
  color: var(--color-muted);
}

.composer {
  border-top: 1px solid var(--color-border);
  background: #fff;
  display: grid;
  gap: 10px;
  padding: 14px min(7vw, 72px) 16px;
}

.composer-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.composer-tools .select {
  width: auto;
  min-width: 170px;
}

.composer-input {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 52px;
  gap: 10px;
}

.composer-input textarea {
  width: 100%;
  min-height: 74px;
  max-height: 170px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  resize: vertical;
  padding: 11px;
}

.send-button {
  border: 0;
  border-radius: 8px;
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
  font-size: 22px;
  font-weight: 900;
}

.session-panel {
  border-left: 1px solid var(--color-border);
  background: #fbfffd;
  overflow: auto;
  padding: 18px;
}

.session-section {
  display: grid;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 0 0 18px;
  margin-bottom: 18px;
}

.session-section:last-child {
  border-bottom: 0;
  margin-bottom: 0;
}

.panel-heading {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
}

.panel-heading h2,
.session-section h2 {
  font-size: 18px;
  margin: 4px 0 0;
}

.session-list,
.note-list,
.note-form {
  display: grid;
  gap: 9px;
}

.session-list button {
  text-align: left;
}

.session-list button.active {
  border-color: var(--color-primary-bright);
  background: var(--color-primary-soft);
}

.progress-strip {
  height: 32px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  padding: 0 12px;
  font-weight: 900;
}

.complete-button,
.next-link,
.note-form button {
  width: 100%;
  justify-content: center;
}

.note-form textarea {
  min-height: 118px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  resize: vertical;
  padding: 10px;
}

.note-card,
.empty-state {
  border: 1px dashed var(--color-border-strong);
  border-radius: 8px;
  background: var(--color-surface-muted);
  padding: 10px;
}

.note-card p {
  margin: 0 0 8px;
}

.note-card button {
  border: 0;
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
  font-weight: 800;
  padding: 0;
}

.muted {
  color: var(--color-muted);
}

@media (max-width: 1100px) {
  .chapter-workbench {
    grid-template-columns: 72px minmax(0, 1fr);
  }

  .chapter-sidebar:not(.collapsed) {
    position: fixed;
    top: 58px;
    bottom: 0;
    left: 0;
    z-index: 20;
    width: min(310px, 86vw);
    box-shadow: 18px 0 46px rgba(15, 118, 110, 0.16);
  }

  .session-panel {
    grid-column: 2;
    min-height: auto;
    border-left: 0;
    border-top: 1px solid var(--color-border);
  }
}

@media (max-width: 760px) {
  .chapter-workbench {
    grid-template-columns: 1fr;
    margin-inline: -16px;
  }

  .chapter-sidebar {
    min-height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .chat-thread,
  .composer {
    padding-inline: 14px;
  }

  .message-row,
  .message-row.user {
    grid-template-columns: 1fr;
  }

  .message-row.user .message-avatar,
  .message-row.user .message-bubble {
    grid-column: auto;
    grid-row: auto;
  }
}
</style>
