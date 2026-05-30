<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

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
  chapters?: ChapterStudyChapter[]
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
const chatThreadRef = ref<HTMLElement | null>(null)

const loading = ref(false)
const loadingMentor = ref(false)
const askingMentor = ref(false)
const mentorAbortController = ref<AbortController | null>(null)
const savingNote = ref(false)
const completing = ref(false)
const generatingQuiz = ref(false)
const deletingSessionId = ref<string | null>(null)
const chapterRailCollapsed = ref(false)
const webSearchEnabled = ref(false)
const renameSessionTarget = ref<MentorSession | null>(null)
const renameSessionTitle = ref('')
const noteComposerOpen = ref(false)
const selectedNote = ref<ChapterAnnotation | null>(null)

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
const bodyClassName = 'chapter-study-page'

const introMessage = computed(() => {
  if (!chapter.value) return ''
  return [
    'I am your chapter AI Mentor.',
    `This chapter focuses on **${displayTitle(chapter.value.title)}**.`,
    `Goal: ${chapter.value.goal}`,
    'Ask a question directly, or ask what to learn next. I will continue at your pace.'
  ].join('\n\n')
})

function protectedHeaders() {
  return DEV_AUTH_HEADERS
}

function appendBackendMessage(base: string, error: unknown) {
  if (error instanceof Error && error.message) return `${base} ${error.message}`
  return base
}

function isAbortError(error: unknown) {
  return error instanceof Error && error.name === 'AbortError'
}

function scrollChatToLatest() {
  void nextTick(() => {
    const run = () => {
      const thread = chatThreadRef.value
      if (!thread) return
      thread.scrollTop = thread.scrollHeight
    }
    if (typeof window !== 'undefined' && window.requestAnimationFrame) {
      window.requestAnimationFrame(run)
    } else {
      run()
    }
  })
}

function noteContent(note: ChapterAnnotation) {
  return note.content?.trim() || 'Untitled note'
}

function notePreview(note: ChapterAnnotation) {
  const content = noteContent(note).replace(/\s+/g, ' ')
  return content.length > 84 ? `${content.slice(0, 84)}...` : content
}

function noteDate(note: ChapterAnnotation) {
  const value = note.updated_at || note.created_at
  if (!value) return ''
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(value))
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

function displayTitle(value?: string | null) {
  return (value ?? '')
    .replace(/^\s{0,3}#{1,6}\s+/, '')
    .replace(/\*\*/g, '')
    .trim()
}

async function loadChapter() {
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await $fetch<ChapterStudyDetail>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}`,
      { headers: protectedHeaders() }
    )
    if (detail.value.chapters?.length) {
      chapterNavigation.value = detail.value.chapters
    } else {
      await loadChapterNavigation(detail.value.chapter.study_space_id)
    }
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
    noteComposerOpen.value = false
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
    if (selectedNote.value?.id === annotation.id) selectedNote.value = null
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to delete annotation.', error)
  }
}

function openNoteComposer() {
  noteComposerOpen.value = true
}

function closeNoteComposer() {
  if (savingNote.value) return
  noteComposerOpen.value = false
}

function openNoteDetail(note: ChapterAnnotation) {
  selectedNote.value = note
}

function closeNoteDetail() {
  selectedNote.value = null
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
  scrollChatToLatest()
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
    if (!mentorSessions.value.length) {
      await createMentorSession()
      return
    }
    const selectedSessionId = preferredSessionId()
    mentorSession.value = mentorSessions.value.find(session => session.id === selectedSessionId) ?? mentorSessions.value[0] ?? null
    if (mentorSession.value) {
      await loadMentorMessages(mentorSession.value.id)
    } else {
      mentorMessages.value = []
      scrollChatToLatest()
    }
  } catch (error) {
    mentorErrorMessage.value = appendBackendMessage('Failed to load mentor session.', error)
  } finally {
    loadingMentor.value = false
  }
}

async function selectMentorSession(session: MentorSession) {
  mentorSession.value = session
  await loadMentorMessages(session.id)
}

async function ensureMentorSession() {
  if (mentorSession.value) return mentorSession.value
  return createMentorSession()
}

async function createMentorSession() {
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
  scrollChatToLatest()
  return session
}

async function createNewSession() {
  if (!confirm('Create a new mentor session?')) return null
  return createMentorSession()
}

function openRenameSessionModal(session: MentorSession) {
  renameSessionTarget.value = session
  renameSessionTitle.value = displayTitle(session.title) || 'Chapter session'
}

function closeRenameSessionModal() {
  renameSessionTarget.value = null
  renameSessionTitle.value = ''
}

async function renameMentorSession() {
  const session = renameSessionTarget.value
  if (!session) return
  const currentTitle = displayTitle(session.title) || 'Chapter session'
  const nextTitle = renameSessionTitle.value.trim()
  if (!nextTitle || nextTitle === currentTitle) return

  mentorErrorMessage.value = ''
  try {
    const renamed = await $fetch<MentorSession>(
      `${config.public.apiBaseUrl}/sessions/${session.id}`,
      {
        method: 'PATCH',
        headers: protectedHeaders(),
        body: { title: nextTitle }
      }
    )
    mentorSessions.value = mentorSessions.value.map(item => (
      item.id === renamed.id ? { ...item, ...renamed } : item
    ))
    if (mentorSession.value?.id === renamed.id) {
      mentorSession.value = { ...mentorSession.value, ...renamed }
    }
    closeRenameSessionModal()
  } catch (error) {
    mentorErrorMessage.value = appendBackendMessage('Failed to rename session.', error)
  }
}

async function deleteMentorSession(session: MentorSession) {
  if (!confirm('Delete this session and its saved messages?')) return

  deletingSessionId.value = session.id
  mentorErrorMessage.value = ''
  try {
    await $fetch(`${config.public.apiBaseUrl}/sessions/${session.id}`, {
      method: 'DELETE',
      headers: protectedHeaders()
    })
    const remainingSessions = mentorSessions.value.filter(item => item.id !== session.id)
    mentorSessions.value = remainingSessions

    if (mentorSession.value?.id === session.id) {
      const nextSession = remainingSessions[0] ?? null
      mentorSession.value = nextSession
      if (nextSession) {
        await loadMentorMessages(nextSession.id)
      } else {
        mentorMessages.value = []
        scrollChatToLatest()
      }
    }
  } catch (error) {
    mentorErrorMessage.value = appendBackendMessage('Failed to delete session.', error)
  } finally {
    deletingSessionId.value = null
  }
}

async function askMentor() {
  const question = mentorQuestion.value.trim()
  if (!question || askingMentor.value) return

  askingMentor.value = true
  mentorErrorMessage.value = ''
  const abortController = new AbortController()
  mentorAbortController.value = abortController
  try {
    const session = await ensureMentorSession()
    mentorMessages.value = [...mentorMessages.value, localUserMessage(session.id, question)]
    scrollChatToLatest()
    mentorQuestion.value = ''
    const answer = await $fetch<MentorMessage>(
      `${config.public.apiBaseUrl}/sessions/${session.id}/messages`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { content: question, web_search_enabled: webSearchEnabled.value },
        signal: abortController.signal
      }
    )
    mentorMessages.value = [...mentorMessages.value, answer]
    scrollChatToLatest()
  } catch (error) {
    if (isAbortError(error)) return
    mentorErrorMessage.value = appendBackendMessage('Failed to ask mentor.', error)
  } finally {
    if (mentorAbortController.value === abortController) {
      mentorAbortController.value = null
    }
    askingMentor.value = false
  }
}

function stopMentorGeneration() {
  mentorAbortController.value?.abort()
}

async function completeCurrentChapter() {
  if (!chapter.value || isCompleted.value) return
  if (!confirm('Mark this chapter as complete?')) return
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
  document.body.classList.add(bodyClassName)
  loadChapter()
  loadMentorSession()
  loadMastery()
  loadAnnotations()
})

onBeforeUnmount(() => {
  document.body.classList.remove(bodyClassName)
})
</script>

<template>
  <section class="chapter-workbench page-enter" :class="{ 'rail-is-collapsed': chapterRailCollapsed }">
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
              <strong>{{ displayTitle(item.title) }}</strong>
            </NuxtLink>
          </nav>
        </template>
      </aside>

      <main class="chat-workspace">
        <header class="chat-topbar">
          <div class="chapter-breadcrumb">
            <span>{{ displayTitle(detail.route.title) }}</span>
            <span aria-hidden="true">/</span>
            <h1>{{ displayTitle(chapter.title) }}</h1>
          </div>
          <NuxtLink v-if="detail.next_chapter_id" class="next-link topbar-next-link" :to="`/chapters/${detail.next_chapter_id}`">
            Next chapter
          </NuxtLink>
        </header>

        <section ref="chatThreadRef" class="chat-thread" aria-live="polite">
          <article class="message-row assistant">
            <div class="message-avatar">AI</div>
            <div class="message-bubble">
              <div class="markdown-body" v-html="renderMarkdown(introMessage)" />
              <div class="message-actions">
                <button class="fork-action" type="button" aria-label="Fork checkpoint" title="Fork checkpoint">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M7 4v7a4 4 0 0 0 4 4h6" />
                    <path d="M7 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z" />
                    <path d="M17 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z" />
                    <path d="M15 9h4v4" />
                    <path d="m19 9-5 5" />
                  </svg>
                </button>
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
                <button class="fork-action" type="button" aria-label="Fork checkpoint" title="Fork checkpoint">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M7 4v7a4 4 0 0 0 4 4h6" />
                    <path d="M7 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z" />
                    <path d="M17 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z" />
                    <path d="M15 9h4v4" />
                    <path d="m19 9-5 5" />
                  </svg>
                </button>
              </div>
            </div>
          </article>
        </section>

        <p v-if="mentorErrorMessage" class="error-alert">{{ mentorErrorMessage }}</p>
        <form class="mentor-form composer" @submit.prevent="askMentor">
          <div class="composer-tools">
            <button class="composer-icon-button" type="button" aria-label="Add attachment">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 5v14" />
                <path d="M5 12h14" />
              </svg>
            </button>
            <button
              data-testid="web-search-toggle"
              class="composer-icon-button web-search-toggle"
              type="button"
              :class="{ active: webSearchEnabled }"
              :aria-pressed="webSearchEnabled"
              :aria-label="webSearchEnabled ? 'Disable web search' : 'Enable web search'"
              title="联网补充，不属于上传资料"
              @click="webSearchEnabled = !webSearchEnabled"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="9" />
                <path d="M3 12h18" />
                <path d="M12 3a14 14 0 0 1 0 18" />
                <path d="M12 3a14 14 0 0 0 0 18" />
              </svg>
            </button>
            <select class="select" aria-label="Model">
              <option>Default model</option>
              <option>Fast tutor</option>
              <option>Deep tutor</option>
            </select>
            <select class="select" aria-label="Thinking strength">
              <option>Normal thinking</option>
              <option>Deep thinking</option>
            </select>
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
              :class="{ 'is-stopping': askingMentor }"
              :type="askingMentor ? 'button' : 'submit'"
              :aria-label="askingMentor ? 'Interrupt generation' : 'Send message'"
              @click="askingMentor && stopMentorGeneration()"
            >
              <svg v-if="askingMentor" viewBox="0 0 24 24" aria-hidden="true">
                <rect x="7" y="7" width="10" height="10" rx="2" />
              </svg>
              <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 19V5" />
                <path d="m6 11 6-6 6 6" />
              </svg>
            </button>
          </div>
        </form>
      </main>

      <aside class="session-panel">
        <section class="session-section">
          <div class="panel-heading">
            <div>
              <p>Sessions</p>
            </div>
            <button data-testid="new-mentor-session" type="button" @click="createNewSession">New</button>
          </div>
          <div class="session-list">
            <div
              v-for="session in mentorSessions"
              :key="session.id"
              class="session-list-row"
              :class="{ active: mentorSession?.id === session.id }"
            >
              <button
                class="session-select"
                type="button"
                @click="selectMentorSession(session)"
              >
                {{ displayTitle(session.title) || 'Chapter session' }}
              </button>
              <button
                data-testid="rename-mentor-session"
                class="session-rename"
                type="button"
                :aria-label="`Rename session ${displayTitle(session.title) || 'Chapter session'}`"
                @click.stop="openRenameSessionModal(session)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0 0-3L17.5 5.5a2.1 2.1 0 0 0-3 0L4 16v4Z" />
                  <path d="m13.5 6.5 4 4" />
                </svg>
              </button>
              <button
                class="session-delete"
                type="button"
                :aria-label="`Delete session ${displayTitle(session.title) || 'Chapter session'}`"
                :disabled="deletingSessionId === session.id"
                @click.stop="deleteMentorSession(session)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M3 6h18" />
                  <path d="M8 6V4h8v2" />
                  <path d="M6 6l1 15h10l1-15" />
                  <path d="M10 11v6" />
                  <path d="M14 11v6" />
                </svg>
              </button>
            </div>
          </div>
        </section>

        <section class="session-section">
          <div class="panel-heading progress-heading">
            <p>Progress</p>
            <button
              data-testid="complete-chapter"
              class="complete-button"
              type="button"
              :aria-label="isCompleted ? 'Chapter completed' : completing ? 'Completing chapter' : 'Mark chapter complete'"
              :title="isCompleted ? 'Completed' : completing ? 'Completing...' : 'Mark complete'"
              :disabled="isCompleted || completing"
              @click="completeCurrentChapter"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m5 12 4 4L19 6" />
              </svg>
            </button>
          </div>
          <div class="progress-strip">
            <span>{{ chapter.status }}</span>
          </div>
          <p>{{ chapter.estimated_days }} estimated days - Mastery: {{ masteryLabel }}</p>
          <button
            data-testid="generate-quiz"
            class="quiz-button"
            type="button"
            :disabled="generatingQuiz"
            @click="generateQuiz"
          >
            {{ generatingQuiz ? 'Generating...' : 'Generate quiz' }}
          </button>
        </section>

        <section class="session-section">
          <div class="panel-heading">
            <div>
              <p>Study notes</p>
              <h2>Personal notes</h2>
            </div>
            <button data-testid="open-note-composer" type="button" @click="openNoteComposer">New</button>
          </div>
          <div v-if="notes.length" class="note-list">
            <article v-for="note in notes" :key="note.id" class="note-card">
              <button class="note-open" type="button" :aria-label="`Open note ${noteContent(note)}`" @click="openNoteDetail(note)">
                <span>{{ notePreview(note) }}</span>
                <small v-if="noteDate(note)">{{ noteDate(note) }}</small>
              </button>
              <button class="note-delete" type="button" :aria-label="`Delete note ${noteContent(note)}`" @click.stop="deleteAnnotation(note)">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M3 6h18" />
                  <path d="M8 6V4h8v2" />
                  <path d="M6 6l1 15h10l1-15" />
                  <path d="M10 11v6" />
                  <path d="M14 11v6" />
                </svg>
              </button>
            </article>
          </div>
          <button v-else class="empty-state note-empty-action" type="button" @click="openNoteComposer">No notes yet. Create one</button>
        </section>
      </aside>

      <div v-if="noteComposerOpen" class="modal-backdrop note-modal-backdrop" @click.self="closeNoteComposer">
        <section class="note-modal" role="dialog" aria-modal="true" aria-labelledby="new-note-title">
          <header class="note-modal-header">
            <div>
              <p class="eyebrow">Study note</p>
              <h2 id="new-note-title">New note</h2>
            </div>
            <button class="note-modal-close" type="button" aria-label="Close note dialog" @click="closeNoteComposer">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 6l12 12" />
                <path d="M18 6 6 18" />
              </svg>
            </button>
          </header>
          <form class="note-form" @submit.prevent="createNote">
            <textarea
              v-model="noteDraft"
              data-testid="chapter-note-input"
              placeholder="Capture the point you want to remember"
              :disabled="savingNote"
            />
            <div class="note-modal-actions">
              <button class="secondary-button" type="button" :disabled="savingNote" @click="closeNoteComposer">Cancel</button>
              <button
                data-testid="save-chapter-note"
                class="primary-button"
                type="submit"
                :disabled="!canSaveNote"
              >
                {{ savingNote ? 'Saving...' : 'Save note' }}
              </button>
            </div>
          </form>
        </section>
      </div>

      <div v-if="selectedNote" class="modal-backdrop note-modal-backdrop" @click.self="closeNoteDetail">
        <section class="note-modal note-detail-modal" role="dialog" aria-modal="true" aria-labelledby="note-detail-title">
          <header class="note-modal-header">
            <div>
              <p class="eyebrow">Study note</p>
              <h2 id="note-detail-title">Note detail</h2>
            </div>
            <button class="note-modal-close" type="button" aria-label="Close note detail" @click="closeNoteDetail">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 6l12 12" />
                <path d="M18 6 6 18" />
              </svg>
            </button>
          </header>
          <div class="note-detail-body">
            <p>{{ noteContent(selectedNote) }}</p>
          </div>
          <footer class="note-modal-actions">
            <button class="secondary-button" type="button" @click="closeNoteDetail">Close</button>
            <button class="danger-button" type="button" @click="deleteAnnotation(selectedNote)">Delete</button>
          </footer>
        </section>
      </div>

      <div v-if="renameSessionTarget" class="modal-backdrop session-rename-backdrop" @click.self="closeRenameSessionModal">
        <section class="session-rename-modal" role="dialog" aria-modal="true" aria-labelledby="rename-session-title">
          <header class="session-rename-header">
            <div>
              <p class="eyebrow">Session</p>
              <h2 id="rename-session-title">Rename session</h2>
            </div>
            <button class="session-rename-close" type="button" aria-label="Close rename dialog" @click="closeRenameSessionModal">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 6l12 12" />
                <path d="M18 6 6 18" />
              </svg>
            </button>
          </header>
          <form class="session-rename-form" @submit.prevent="renameMentorSession">
            <label class="form-field">
              Name
              <input v-model="renameSessionTitle" data-testid="rename-session-input" class="input" maxlength="160" autofocus>
            </label>
            <div class="session-rename-actions">
              <button class="secondary-button" type="button" @click="closeRenameSessionModal">Cancel</button>
              <button class="primary-button" type="submit" :disabled="!renameSessionTitle.trim()">Save</button>
            </div>
          </form>
        </section>
      </div>
    </template>
  </section>
</template>

<style scoped>
.chapter-workbench {
  width: min(100%, 1600px);
  height: calc(100dvh - 58px - 42px);
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr) minmax(280px, 360px);
  gap: 16px;
  overflow: hidden;
  padding-top: 12px;
}

:global(body.chapter-study-page) {
  overflow: hidden;
}

.chapter-workbench {
  background: #f5fbf9;
}

.chapter-sidebar,
.chat-workspace,
.session-panel {
  min-height: 0;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: var(--shadow-card);
}

.chapter-sidebar,
.session-panel {
  backdrop-filter: blur(12px);
}

.chapter-sidebar {
  background:
    linear-gradient(180deg, rgba(236, 253, 245, 0.8), rgba(255, 255, 255, 0.92)),
    var(--color-surface);
  padding: 16px;
  overflow: auto;
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
  overflow: hidden;
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
  scrollbar-gutter: stable;
  padding: 22px min(7vw, 72px);
  overscroll-behavior: contain;
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
  position: sticky;
  top: 12px;
  height: calc(100dvh - 58px - 42px - 12px);
  background: rgba(251, 255, 253, 0.96);
  overflow: auto;
  scrollbar-gutter: stable;
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
  justify-content: center;
  padding: 0 12px;
  text-align: center;
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
    height: auto;
    min-height: calc(100dvh - 58px - 42px);
    overflow: visible;
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
    min-height: 0;
    position: relative;
    top: auto;
    height: auto;
  }
}

@media (max-width: 760px) {
  .chapter-workbench {
    grid-template-columns: 1fr;
    height: auto;
    min-height: calc(100dvh - 58px - 42px);
    overflow: visible;
  }

  .chapter-sidebar {
    min-height: auto;
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

  .session-panel {
    grid-column: 1;
    position: relative;
    top: auto;
    height: auto;
  }
}

/* Taste pass: make the study screen feel like one focused chat workspace, not stacked cards. */
.chapter-workbench {
  width: min(100%, 1720px);
  height: calc(100dvh - 58px - 24px);
  grid-template-columns: 286px minmax(0, 1fr) minmax(300px, 342px);
  gap: 0;
  padding-top: 8px;
  background: transparent;
}

.chapter-workbench.rail-is-collapsed {
  grid-template-columns: 58px minmax(0, 1fr) minmax(300px, 342px);
}

.chapter-sidebar,
.chat-workspace,
.session-panel {
  border-radius: 0;
  box-shadow: none;
}

.chapter-sidebar {
  border: 0;
  border-right: 1px solid rgba(142, 202, 191, 0.55);
  background: linear-gradient(180deg, rgba(236, 253, 245, 0.75), rgba(248, 253, 251, 0.96));
  padding: 12px;
}

.chapter-sidebar.collapsed {
  width: auto;
  min-width: 0;
  padding-inline: 8px;
}

.rail-collapse {
  width: 34px;
  height: 34px;
  border: 0;
  background: transparent;
  color: #0f766e;
  font-size: 15px;
}

.rail-collapse:hover {
  background: rgba(20, 184, 166, 0.1);
}

.rail-title {
  margin: 14px 0 18px;
}

.chapter-list {
  gap: 3px;
}

.chapter-link {
  border: 0;
  border-left: 3px solid transparent;
  border-radius: 0;
  padding: 10px 9px;
}

.chapter-link:hover,
.chapter-link.active {
  border-color: #14b8a6;
  background: rgba(255, 255, 255, 0.72);
}

.chapter-link span {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  background: #0f766e;
}

.chat-workspace {
  border: 0;
  background:
    radial-gradient(circle at 50% -12%, rgba(20, 184, 166, 0.09), transparent 28%),
    #fbfffd;
}

.chat-topbar {
  min-height: 66px;
  border-bottom: 1px solid rgba(142, 202, 191, 0.45);
  padding: 10px clamp(18px, 4vw, 48px);
}

.chat-topbar h1 {
  font-size: clamp(20px, 2vw, 28px);
  letter-spacing: 0;
}

.quiz-button,
.complete-button,
.next-link,
.panel-heading button,
.note-form button,
.session-list button,
.composer-tools button,
.message-actions button {
  border-radius: 7px;
  box-shadow: none;
}

.chat-thread {
  gap: 20px;
  padding: 24px clamp(24px, 6vw, 94px);
  background:
    linear-gradient(90deg, transparent 0, transparent calc(100% - 1px), rgba(142, 202, 191, 0.28) calc(100% - 1px));
}

.message-row {
  grid-template-columns: 34px minmax(0, 860px);
}

.message-row.user {
  grid-template-columns: minmax(0, 760px) 34px;
}

.message-avatar {
  width: 30px;
  height: 30px;
  border-radius: 7px;
  background: #0f766e;
  font-size: 11px;
}

.message-bubble {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 2px 0 14px;
}

.message-row.user .message-bubble {
  border-left: 3px solid rgba(20, 184, 166, 0.55);
  background: rgba(236, 253, 245, 0.62);
  padding: 12px 14px;
}

.message-actions {
  justify-content: flex-start;
  opacity: 0.72;
}

.citation-card {
  border-radius: 0;
  border: 0;
  border-left: 2px solid rgba(20, 184, 166, 0.45);
  background: rgba(236, 253, 245, 0.55);
}

.composer {
  border-top: 1px solid rgba(142, 202, 191, 0.45);
  background: rgba(251, 255, 253, 0.92);
  padding: 12px clamp(18px, 4vw, 48px);
}

.composer-input {
  grid-template-columns: minmax(0, 1fr) 46px;
}

.composer-input textarea {
  min-height: 62px;
  border-radius: 7px;
  background: #ffffff;
}

.send-button {
  border-radius: 7px;
}

.session-panel {
  top: 8px;
  height: calc(100dvh - 58px - 24px - 8px);
  border: 0;
  border-left: 1px solid rgba(142, 202, 191, 0.55);
  background: rgba(248, 253, 251, 0.88);
  padding: 14px;
}

.session-section {
  gap: 10px;
  border-bottom-color: rgba(142, 202, 191, 0.45);
  margin-bottom: 14px;
  padding-bottom: 14px;
}

.session-list button {
  border: 0;
  border-left: 3px solid transparent;
  border-radius: 0;
  background: transparent;
}

.session-list button.active {
  border-color: #14b8a6;
  background: rgba(204, 251, 241, 0.52);
}

.note-card,
.empty-state {
  border-radius: 0;
  border-color: rgba(142, 202, 191, 0.55);
  background: rgba(236, 253, 245, 0.48);
}

@media (max-width: 1100px) {
  .chapter-workbench,
  .chapter-workbench.rail-is-collapsed {
    grid-template-columns: 58px minmax(0, 1fr);
    gap: 0;
  }

  .chapter-sidebar:not(.collapsed) {
    border-right: 1px solid rgba(142, 202, 191, 0.55);
    box-shadow: 18px 0 46px rgba(15, 118, 110, 0.1);
  }

  .session-panel {
    grid-column: 2;
    height: auto;
    border-top: 1px solid rgba(142, 202, 191, 0.45);
    border-left: 0;
  }
}

@media (max-width: 760px) {
  .chapter-workbench,
  .chapter-workbench.rail-is-collapsed {
    grid-template-columns: 1fr;
    height: auto;
  }

  .chapter-sidebar {
    border-right: 0;
    border-bottom: 1px solid rgba(142, 202, 191, 0.55);
  }

  .chat-thread {
    padding-inline: 16px;
  }
}

/* Codex-inspired dark chat pass. */
:global(body.chapter-study-page) {
  background: #121413;
}

:global(body.chapter-study-page .app-topbar) {
  border-bottom-color: rgba(255, 255, 255, 0.08);
  background: rgba(18, 20, 19, 0.9);
  color: #eef5f1;
}

:global(body.chapter-study-page .brand-icon),
:global(body.chapter-study-page .avatar-button) {
  background: #0f766e;
  color: #f8fffc;
}

:global(body.chapter-study-page .icon-button) {
  border-color: rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.04);
  color: #d9e6e1;
}

.chapter-workbench {
  width: 100%;
  height: calc(100dvh - 58px);
  padding-top: 0;
  color: #e7efeb;
}

.chapter-sidebar {
  border-right-color: rgba(255, 255, 255, 0.08);
  background: #171c20;
}

.rail-collapse,
.chapter-link,
.rail-title strong {
  color: #e7efeb;
}

.rail-title span,
.chat-topbar p,
.panel-heading p,
.session-section > p {
  color: #8b9993;
}

.chapter-link:hover,
.chapter-link.active {
  background: rgba(255, 255, 255, 0.06);
  border-color: #14b8a6;
}

.chapter-link span,
.message-avatar {
  background: #0f766e;
  color: #f7fffc;
}

.chat-workspace {
  background:
    radial-gradient(circle at 50% 0%, rgba(20, 184, 166, 0.08), transparent 24%),
    #121413;
}

.chat-topbar {
  min-height: 76px;
  border-bottom-color: rgba(255, 255, 255, 0.08);
  padding-inline: clamp(28px, 5vw, 74px);
}

.chat-topbar h1,
.markdown-body,
.panel-heading h2,
.session-section h2 {
  color: #f3faf6;
}

.quiz-button {
  border-color: rgba(20, 184, 166, 0.56);
  background: #0f766e;
  color: #f7fffc;
}

.chat-thread {
  background: transparent;
  padding: 28px clamp(36px, 12vw, 210px) 22px;
}

.message-bubble {
  color: #e7efeb;
}

.message-row.user .message-bubble {
  border-left-color: rgba(20, 184, 166, 0.75);
  background: rgba(20, 184, 166, 0.11);
}

.message-actions button {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #9ecdc3;
}

.citation-card {
  background: rgba(255, 255, 255, 0.04);
  color: #dbe7e2;
}

.composer {
  width: min(880px, calc(100% - 72px));
  justify-self: center;
  position: relative;
  display: block;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 18px;
  background: #2a2c2b;
  box-shadow: 0 22px 80px rgba(0, 0, 0, 0.35);
  margin: 0 auto 18px;
  padding: 0;
}

.composer-tools {
  position: absolute;
  left: 14px;
  right: 76px;
  bottom: 12px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}

.composer-icon-button,
.composer-tools button {
  width: 34px;
  height: 34px;
  min-height: 34px;
  display: inline-grid;
  place-items: center;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: #c9d6d1;
  cursor: pointer;
  font-size: 24px;
  font-weight: 400;
  padding: 0;
}

.composer-icon-button:hover,
.composer-tools button:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.composer-icon-button svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.composer-tools .select {
  width: auto;
  min-width: 132px;
  height: 34px;
  min-height: 34px;
  border: 0;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.06);
  color: #dfe8e4;
  padding: 0 30px 0 10px;
}

.composer-tools .select:first-of-type {
  margin-left: auto;
}

.composer-input {
  display: block;
  position: relative;
}

.composer-input textarea {
  min-height: 112px;
  max-height: 220px;
  border: 0;
  border-radius: 18px;
  background: transparent;
  color: #f4faf7;
  line-height: 1.5;
  padding: 20px 64px 60px 18px;
  resize: none;
}

.composer-input textarea::placeholder {
  color: #858d89;
}

.composer-input textarea:focus {
  outline: none;
  box-shadow: none;
}

.send-button {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 3;
  width: 38px;
  height: 38px;
  border-radius: 999px;
  background: #d8ddda;
  color: #172321;
  font-size: 21px;
}

.send-button:hover {
  background: #f4faf7;
}

.send-button:disabled {
  opacity: 0.45;
}

.session-panel {
  height: calc(100dvh - 58px);
  top: 0;
  border-left-color: rgba(255, 255, 255, 0.08);
  background: #171817;
  color: #dfe8e4;
}

.session-section {
  border-bottom-color: rgba(255, 255, 255, 0.1);
}

.session-list button,
.complete-button,
.next-link,
.note-form button {
  border-color: rgba(255, 255, 255, 0.11);
  background: rgba(255, 255, 255, 0.04);
  color: #9de7d8;
}

.session-list button.active {
  background: rgba(20, 184, 166, 0.14);
  color: #8ff2df;
}

.progress-strip {
  background: rgba(20, 184, 166, 0.18);
  color: #8ff2df;
}

.note-form textarea {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #f3faf6;
}

.note-card,
.empty-state {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #aebbb6;
}

@media (max-width: 900px) {
  .composer {
    width: calc(100% - 28px);
  }

  .composer-tools {
    right: 64px;
    overflow-x: auto;
  }

  .composer-tools .select {
    min-width: 118px;
  }
}

/* Keep the Codex composer shape, but return the chapter page to a fresh light palette. */
:global(body.chapter-study-page) {
  background: #f4fbf9;
}

:global(body.chapter-study-page .app-topbar) {
  border-bottom-color: rgba(161, 211, 202, 0.58);
  background: rgba(246, 251, 249, 0.9);
  color: var(--color-text);
}

:global(body.chapter-study-page .icon-button) {
  border-color: rgba(20, 184, 166, 0.38);
  background: rgba(255, 255, 255, 0.72);
  color: var(--color-text);
}

.chapter-workbench {
  color: var(--color-text);
}

.chapter-sidebar {
  border-right-color: rgba(142, 202, 191, 0.55);
  background: linear-gradient(180deg, rgba(236, 253, 245, 0.76), rgba(248, 253, 251, 0.96));
}

.rail-collapse,
.chapter-link,
.rail-title strong,
.chat-topbar h1,
.markdown-body,
.panel-heading h2,
.session-section h2 {
  color: var(--color-text);
}

.rail-title span,
.chat-topbar p,
.panel-heading p,
.session-section > p {
  color: var(--color-muted);
}

.chapter-link:hover,
.chapter-link.active {
  background: rgba(255, 255, 255, 0.72);
}

.chat-workspace {
  background:
    radial-gradient(circle at 50% 0%, rgba(20, 184, 166, 0.11), transparent 28%),
    #fbfffd;
}

.chat-topbar {
  border-bottom-color: rgba(142, 202, 191, 0.45);
}

.message-bubble {
  color: var(--color-text);
}

.message-row.user .message-bubble {
  border-left-color: rgba(20, 184, 166, 0.55);
  background: rgba(236, 253, 245, 0.62);
}

.message-actions button {
  border-color: rgba(161, 211, 202, 0.62);
  background: rgba(255, 255, 255, 0.74);
  color: #0f766e;
}

.citation-card {
  background: rgba(236, 253, 245, 0.55);
  color: var(--color-text);
}

.composer {
  border-color: rgba(20, 184, 166, 0.22);
  background: #f8fdfb;
  box-shadow: 0 18px 55px rgba(15, 118, 110, 0.14);
}

.composer-icon-button,
.composer-tools button {
  color: #0f766e;
}

.composer-icon-button:hover,
.composer-tools button:hover {
  background: rgba(20, 184, 166, 0.1);
  color: #0f766e;
}

.web-search-toggle svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}

.web-search-toggle.active {
  background: #0f766e;
  color: #ffffff;
}

.web-search-toggle.active:hover {
  background: #0d9488;
  color: #ffffff;
}

.composer-tools .select {
  background: rgba(204, 251, 241, 0.44);
  color: var(--color-text);
  width: 138px;
  min-width: 0;
  padding-right: 24px;
}

.composer-input textarea {
  color: var(--color-text);
}

.composer-input textarea::placeholder {
  color: #6d817c;
}

.send-button {
  background: #0f766e;
  color: #ffffff;
}

.send-button:hover {
  background: #0d9488;
}

.send-button svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.2;
}

.send-button svg rect {
  fill: currentColor;
  stroke: none;
}

.send-button span {
  display: none;
}

.send-button.is-stopping {
  background: #dc2626;
  color: #ffffff;
}

.send-button.is-stopping:hover {
  background: #b91c1c;
}

.session-panel {
  border-left-color: rgba(142, 202, 191, 0.55);
  background: rgba(248, 253, 251, 0.9);
  color: var(--color-text);
}

.session-section {
  border-bottom-color: rgba(142, 202, 191, 0.45);
}

.session-list button,
.complete-button,
.next-link,
.note-form button {
  border-color: rgba(161, 211, 202, 0.62);
  background: rgba(255, 255, 255, 0.78);
  color: #0f766e;
}

.session-list button.active {
  background: rgba(204, 251, 241, 0.6);
  color: #0f766e;
}

.progress-strip {
  background: rgba(204, 251, 241, 0.82);
  color: #0f766e;
}

.note-form textarea {
  border-color: rgba(161, 211, 202, 0.62);
  background: rgba(255, 255, 255, 0.78);
  color: var(--color-text);
}

.note-card,
.empty-state {
  border-color: rgba(142, 202, 191, 0.55);
  background: rgba(236, 253, 245, 0.48);
  color: var(--color-muted);
}

.message-actions {
  align-items: center;
  gap: 6px;
}

.message-actions button {
  min-height: 30px;
  border-radius: 8px;
  background: transparent;
  box-shadow: none;
}

.fork-action {
  width: 32px;
  height: 30px;
  display: inline-grid;
  place-items: center;
  padding: 0;
}

.fork-action svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.interrupt-action {
  padding-inline: 10px;
  font-size: 13px;
}

.message-actions button:hover {
  border-color: rgba(20, 184, 166, 0.35);
  background: rgba(20, 184, 166, 0.08);
}

.session-list-row {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 30px 30px;
  align-items: center;
  border-left: 3px solid transparent;
  transition: background 0.16s ease, border-color 0.16s ease;
}

.session-list-row.active {
  border-color: #14b8a6;
  background: rgba(204, 251, 241, 0.6);
}

.session-list-row:hover,
.session-list-row:focus-within {
  background: rgba(255, 255, 255, 0.78);
}

.session-list {
  min-height: 156px;
  max-height: min(380px, 44dvh);
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.session-list .session-select {
  min-width: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: #0f766e;
  text-align: left;
  box-shadow: none;
}

.session-list .session-select:hover {
  background: transparent;
}

.session-list .session-rename,
.session-list .session-delete {
  width: 28px;
  height: 28px;
  min-height: 28px;
  display: inline-grid;
  place-items: center;
  margin-right: 4px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #dc2626;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.14s ease, background 0.14s ease, color 0.14s ease;
}

.session-list .session-rename {
  color: var(--color-primary);
}

.session-list-row:hover .session-rename,
.session-list-row:focus-within .session-rename,
.session-list-row:hover .session-delete,
.session-list-row:focus-within .session-delete {
  opacity: 1;
  pointer-events: auto;
}

.session-list .session-rename:hover {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.session-list .session-delete:hover {
  background: rgba(220, 38, 38, 0.1);
  color: #b91c1c;
}

.session-rename svg,
.session-delete svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

@media (hover: none) {
  .session-list .session-delete {
    opacity: 1;
    pointer-events: auto;
  }
}

.note-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 30px;
  align-items: start;
  gap: 8px;
}

.note-card p {
  margin-bottom: 0;
}

.note-delete {
  width: 28px;
  height: 28px;
  min-height: 28px;
  display: inline-grid;
  place-items: center;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #dc2626;
  cursor: pointer;
  padding: 0;
}

.note-delete:hover {
  background: rgba(220, 38, 38, 0.1);
  color: #b91c1c;
}

.note-delete svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

/* Rounded center chat canvas. */
.chat-workspace {
  align-self: start;
  height: calc(100dvh - 58px - 24px);
  margin: 12px 0;
  border: 1px solid rgba(125, 190, 180, 0.34);
  border-radius: 18px;
  box-shadow:
    0 18px 52px rgba(15, 118, 110, 0.08),
    0 1px 0 rgba(255, 255, 255, 0.9) inset;
  overflow: hidden;
}

.chapter-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  color: var(--color-muted);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.25;
}

.chapter-breadcrumb h1 {
  margin: 0;
  color: inherit;
  font-size: inherit;
  font-weight: inherit;
  letter-spacing: 0;
}

.chat-topbar {
  border-radius: 18px 18px 0 0;
}

.composer {
  margin-bottom: 14px;
}

/* Floating Codex-style session inspector. */
.session-panel {
  align-self: start;
  box-sizing: border-box;
  height: calc(100dvh - 58px - 24px);
  margin: 12px 14px 12px 10px;
  border: 1px solid rgba(125, 190, 180, 0.42);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(239, 252, 248, 0.82)),
    rgba(248, 253, 251, 0.88);
  box-shadow:
    0 22px 70px rgba(15, 118, 110, 0.16),
    0 1px 0 rgba(255, 255, 255, 0.92) inset;
  backdrop-filter: blur(18px);
  overflow: auto;
  scrollbar-gutter: stable;
}

.session-section:first-child {
  padding-top: 2px;
}

.session-list-row {
  border-radius: 10px;
  border-left: 0;
  padding-left: 0;
}

.session-list-row.active {
  border-color: transparent;
  background: rgba(185, 245, 235, 0.72);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.72) inset;
}

.session-list-row:hover,
.session-list-row:focus-within {
  background: rgba(255, 255, 255, 0.74);
}

.session-list .session-select {
  border-radius: 10px 0 0 10px;
  padding-left: 12px;
}

.session-list .session-rename,
.session-list .session-delete {
  margin-right: 6px;
}

@media (max-width: 1100px) {
  .session-panel {
    margin: 12px 14px 16px;
    height: auto;
    border-radius: 16px;
  }
}

/* Interaction feel pass: subtle Codex-like motion without distracting from reading. */
@media (prefers-reduced-motion: no-preference) {
  .chapter-workbench {
    transition: grid-template-columns 260ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .chapter-sidebar,
  .chat-workspace,
  .session-panel {
    transition:
      border-color 180ms ease,
      box-shadow 220ms ease,
      background 220ms ease,
      margin 260ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .chapter-sidebar {
    transition:
      padding 260ms cubic-bezier(0.22, 1, 0.36, 1),
      border-color 180ms ease,
      background 220ms ease,
      box-shadow 220ms ease;
  }

  .rail-collapse,
  .chapter-link,
  .chapter-link span,
  .quiz-button,
  .complete-button,
  .next-link,
  .panel-heading button,
  .note-form button,
  .composer-icon-button,
  .composer-tools button,
  .composer-tools .select,
  .composer-input textarea,
  .send-button,
  .session-list-row,
  .session-list .session-select,
  .session-delete,
  .note-delete,
  .fork-action {
    transition:
      transform 160ms ease,
      background-color 160ms ease,
      border-color 160ms ease,
      box-shadow 180ms ease,
      color 160ms ease,
      opacity 140ms ease;
  }

  .chapter-link:hover {
    transform: translateX(2px);
  }

  .chapter-link:active,
  .rail-collapse:active,
  .quiz-button:active,
  .complete-button:active,
  .next-link:active,
  .panel-heading button:active,
  .note-form button:active,
  .composer-icon-button:active,
  .send-button:active,
  .session-list-row:active,
  .note-delete:active {
    transform: scale(0.98);
  }

  .rail-collapse:hover,
  .composer-tools .select:hover,
  .composer-icon-button:hover,
  .panel-heading button:hover,
  .note-form button:hover {
    transform: translateY(-1px);
  }

  .composer {
    transition:
      transform 180ms ease,
      border-color 180ms ease,
      box-shadow 220ms ease,
      background-color 180ms ease;
  }

  .composer:focus-within {
    transform: translateY(-1px);
    border-color: rgba(20, 184, 166, 0.45);
    box-shadow: 0 22px 70px rgba(15, 118, 110, 0.18);
  }

  .composer-tools .select:focus,
  .composer-input textarea:focus {
    border-color: rgba(20, 184, 166, 0.52);
    box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.11);
  }

  .send-button:hover {
    transform: translateY(-1px) scale(1.03);
  }

  .session-list-row:hover,
  .session-list-row:focus-within {
    transform: translateX(1px);
  }

  .message-row {
    animation: message-soft-enter 180ms ease both;
  }
}

@keyframes message-soft-enter {
  from {
    opacity: 0;
    transform: translateY(4px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 760px) {
  :global(body.chapter-study-page) {
    overflow: auto;
  }

  .chat-workspace {
    height: auto;
    min-height: calc(100dvh - 58px);
    overflow: visible;
  }
}

.session-rename-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  background: rgba(31, 35, 40, 0.32);
  backdrop-filter: blur(5px);
  padding: 20px;
}

.session-rename-modal {
  width: min(460px, 100%);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  box-shadow: var(--shadow-floating);
  overflow: hidden;
}

.session-rename-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding: 16px;
}

.session-rename-header h2 {
  margin: 0;
  font-size: 18px;
}

.session-rename-close {
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface);
  color: var(--color-muted);
  cursor: pointer;
  display: inline-grid;
  place-items: center;
}

.session-rename-close svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.session-rename-form {
  display: grid;
  gap: 16px;
  padding: 16px;
}

.session-rename-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* Primer redesign pass: chapter study is a one-screen workspace with floating context. */
.chapter-workbench {
  width: 100%;
  height: calc(100dvh - 56px);
  grid-template-columns: 280px minmax(0, 1fr) 328px;
  gap: 0;
  padding: 0;
  background: var(--color-page);
}

.chapter-workbench.rail-is-collapsed {
  grid-template-columns: 56px minmax(0, 1fr) 328px;
}

.chapter-sidebar {
  border: 0;
  border-right: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-surface);
  box-shadow: none;
  padding: 16px;
}

.chapter-sidebar.collapsed {
  width: auto;
  min-width: 0;
  padding: 12px 10px;
}

.rail-collapse {
  border-radius: 6px;
  color: var(--color-muted);
}

.rail-title strong {
  font-size: 15px;
}

.chapter-link {
  border-radius: 6px;
  border-left: 3px solid transparent;
  border-color: transparent;
}

.chapter-link:hover,
.chapter-link.active {
  border-color: transparent;
  border-left-color: var(--color-primary);
  background: var(--color-page);
}

.chapter-link span {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: var(--color-page);
  color: var(--color-muted);
}

.chat-workspace {
  align-self: stretch;
  height: auto;
  margin: 18px 20px;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--color-surface);
  box-shadow: none;
  overflow: hidden;
}

.chat-topbar {
  min-height: 58px;
  border-radius: 16px 16px 0 0;
  border-bottom-color: var(--color-border);
  padding: 12px 16px;
}

.chapter-breadcrumb,
.chapter-breadcrumb h1 {
  color: var(--color-muted);
}

.quiz-button,
.complete-button,
.next-link,
.panel-heading button,
.note-form button {
  border-radius: 6px;
  border-color: var(--color-border);
  color: var(--color-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.quiz-button {
  border-color: rgba(31, 136, 61, 0.24);
  background: var(--color-success);
  color: #fff;
}

.topbar-next-link {
  width: auto;
  min-width: 136px;
  flex: 0 0 auto;
}

.session-section > .quiz-button {
  width: 100%;
}

.chat-thread {
  gap: 18px;
  padding: 22px min(6vw, 72px);
  scroll-behavior: smooth;
}

.message-avatar {
  border-radius: 999px;
  background: var(--color-text);
}

.message-bubble {
  border-color: var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  transition:
    border-color 180ms ease,
    background-color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.message-row.user .message-bubble {
  background: var(--color-primary-soft);
  border-color: #b6e3ff;
}

.citation-card {
  border-color: var(--color-border);
  border-radius: 12px;
  background: var(--color-page);
  overflow: hidden;
  transition:
    border-color 180ms ease,
    background-color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.citation-card:hover {
  border-color: var(--color-border-strong);
  background: var(--color-surface);
  box-shadow: 0 8px 20px rgba(31, 35, 40, 0.06);
  transform: translateY(-1px);
}

.composer {
  margin: 0 18px 18px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  box-shadow: 0 8px 24px rgba(31, 35, 40, 0.08);
}

.composer-tools {
  border-bottom-color: var(--color-border);
}

.composer-icon-button,
.composer-tools button {
  border-radius: 6px;
  color: var(--color-muted);
}

.composer-tools .select {
  width: 132px;
  background: var(--color-page);
  color: var(--color-text);
}

.send-button {
  border-radius: 8px;
  background: var(--color-success);
}

.send-button:hover {
  background: #1a7f37;
}

.send-button.is-stopping {
  background: var(--color-error);
}

.session-panel {
  align-self: stretch;
  height: auto;
  margin: 18px 16px 18px 0;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: var(--shadow-floating);
  backdrop-filter: blur(12px);
}

.session-section {
  border-bottom-color: var(--color-border);
}

.session-list {
  align-content: start;
  grid-auto-rows: max-content;
  gap: 8px;
}

.session-list-row {
  min-height: 38px;
  grid-template-columns: minmax(0, 1fr) 28px 28px;
}

.session-list-row.active {
  background: var(--color-primary-soft);
}

.session-list .session-select {
  min-height: 38px;
  padding: 6px 8px 6px 12px;
  color: var(--color-text);
  line-height: 1.25;
}

.session-list .session-rename,
.session-list .session-delete {
  width: 26px;
  height: 26px;
  min-height: 26px;
  margin-right: 4px;
}

.progress-strip {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.progress-heading {
  align-items: center;
}

.progress-heading > p {
  margin: 0;
}

.progress-heading .complete-button {
  width: 34px;
  height: 34px;
  min-height: 34px;
  flex: 0 0 34px;
  padding: 0;
  color: var(--color-success);
}

.complete-button svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.6;
}

.note-form textarea,
.note-card,
.empty-state {
  border-color: var(--color-border);
  border-radius: 6px;
  background: var(--color-page);
}

.note-list {
  align-content: start;
  max-height: 188px;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.note-card {
  grid-template-columns: minmax(0, 1fr) 28px;
  align-items: center;
  min-height: 42px;
  border-style: solid;
  padding: 0;
  overflow: hidden;
}

.note-open {
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  display: grid;
  gap: 2px;
  font-weight: 600;
  padding: 8px 10px;
  text-align: left;
}

.note-open span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-open small {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 500;
}

.note-card:hover {
  background: var(--color-surface);
}

.note-delete {
  align-self: center;
  width: 26px;
  height: 26px;
  min-height: 26px;
  margin-right: 4px;
}

.note-empty-action {
  width: 100%;
  color: var(--color-muted);
  cursor: pointer;
  text-align: left;
}

.note-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 82;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(31, 35, 40, 0.32);
  backdrop-filter: blur(5px);
}

.note-modal {
  width: min(560px, 100%);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  box-shadow: var(--shadow-floating);
  overflow: hidden;
}

.note-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding: 16px;
}

.note-modal-header h2 {
  margin: 0;
  font-size: 18px;
}

.note-modal-close {
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface);
  color: var(--color-muted);
  cursor: pointer;
  display: inline-grid;
  place-items: center;
}

.note-modal-close svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.note-modal .note-form {
  padding: 16px;
}

.note-modal .note-form textarea {
  min-height: 220px;
  max-height: 46dvh;
}

.note-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px;
}

.note-form .note-modal-actions {
  padding: 0;
}

.note-modal-actions button,
.note-form .note-modal-actions button {
  width: auto;
}

.note-detail-body {
  max-height: 52dvh;
  overflow: auto;
  padding: 18px;
}

.note-detail-body p {
  margin: 0;
  color: var(--color-text);
  line-height: 1.65;
  white-space: pre-wrap;
}

.danger-button {
  min-height: 34px;
  border: 1px solid rgba(207, 34, 46, 0.24);
  border-radius: 6px;
  background: var(--color-surface);
  color: var(--color-error);
  cursor: pointer;
  font-weight: 700;
  padding: 0 12px;
}

.danger-button:hover {
  background: var(--color-error-soft);
}

@media (max-width: 1100px) {
  .chapter-workbench,
  .chapter-workbench.rail-is-collapsed {
    grid-template-columns: 1fr;
    height: auto;
  }

  .chapter-sidebar {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .chat-workspace,
  .session-panel {
    margin: 14px;
  }
}
</style>
