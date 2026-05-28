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

interface ChapterMentorState {
  id: string
  chapter_id: string
  summary: string
  weak_points: string[]
  next_actions: string[]
  evidence: Record<string, unknown>[]
  source_session_count: number
  source_message_count: number
  updated_at?: string
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

interface PlannerAction {
  id: string
  study_space_id: string
  chapter_id: string | null
  source_planner_state_id?: string | null
  action_type: string
  status: string
  title: string
  rationale: string
  payload: Record<string, unknown>
  created_at?: string | null
  updated_at?: string | null
}

interface AgentRunLearningSignal {
  kind: string
  [key: string]: unknown
}

interface AgentRunTimelineItem {
  id?: string
  agent_type: string
  status: string
  summary: string
  node_trace: string[]
  learning_signals: AgentRunLearningSignal[]
  thread_id: string | null
  checkpoint_backend: string | null
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
const mentorState = ref<ChapterMentorState | null>(null)
const updatingMentorState = ref(false)
const mastery = ref<MasteryRecord | null>(null)
const generatingQuiz = ref(false)
const plannerActions = ref<PlannerAction[]>([])
const loadingPlannerActions = ref(false)
const updatingPlannerActionId = ref<string | null>(null)
const agentRuns = ref<AgentRunTimelineItem[]>([])
const loadingAgentRuns = ref(false)

const chapter = computed(() => detail.value?.chapter ?? null)
const evidence = computed(() => detail.value?.evidence ?? [])
const isCompleted = computed(() => chapter.value?.status === 'completed')
const hasMentorState = computed(() => {
  return Boolean(
    mentorState.value?.summary ||
      mentorState.value?.weak_points?.length ||
      mentorState.value?.next_actions?.length
  )
})
const masteryLabel = computed(() => {
  if (!mastery.value) return 'Mastery: not started'
  return `Mastery: ${mastery.value.level} ${mastery.value.score_percent}%`
})
const quizWeakPoint = computed(() => mastery.value?.weak_points?.[0] ?? null)
const activeReviewActions = computed(() => {
  return plannerActions.value.filter(action => {
    return (
      action.chapter_id === chapterId.value &&
      action.action_type === 'review_chapter' &&
      action.status !== 'completed' &&
      action.status !== 'dismissed'
    )
  })
})

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

function normalizePlannerActions(response: PlannerAction[] | { actions?: PlannerAction[] }) {
  return Array.isArray(response) ? response : response.actions ?? []
}

function normalizeAgentRuns(response: { runs?: AgentRunTimelineItem[] } | null | undefined): AgentRunTimelineItem[] {
  return (response?.runs ?? [])
    .filter(run => ['chapter_mentor', 'session_tutor'].includes(run?.agent_type) && run.status)
    .map(run => ({
      ...run,
      summary: run.summary || 'No summary recorded.',
      node_trace: Array.isArray(run.node_trace) ? run.node_trace.filter(Boolean).map(String) : [],
      learning_signals: Array.isArray(run.learning_signals)
        ? run.learning_signals
            .map(signal => (typeof signal === 'string' ? { kind: signal } : signal))
            .filter((signal): signal is AgentRunLearningSignal => Boolean(signal?.kind))
        : [],
      thread_id: run.thread_id ?? null,
      checkpoint_backend: run.checkpoint_backend ?? null
    }))
}

function agentTypeLabel(agentType: string) {
  const labels: Record<string, string> = {
    chapter_mentor: 'L2 Mentor',
    session_tutor: 'L3 Tutor'
  }
  return labels[agentType] ?? agentType
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

async function loadChapter() {
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await $fetch<ChapterStudyDetail>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}`,
      { headers: protectedHeaders() }
    )
    await loadPlannerActions(detail.value.chapter.study_space_id)
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to load chapter.', error)
    plannerActions.value = []
  } finally {
    loading.value = false
  }
}

async function loadPlannerActions(studySpaceId: string) {
  loadingPlannerActions.value = true
  try {
    const response = await $fetch<PlannerAction[] | { actions?: PlannerAction[] }>(
      `${config.public.apiBaseUrl}/study-spaces/${studySpaceId}/planner-actions`,
      { headers: protectedHeaders() }
    )
    plannerActions.value = normalizePlannerActions(response)
  } catch {
    plannerActions.value = []
  } finally {
    loadingPlannerActions.value = false
  }
}

async function loadAgentRuns() {
  loadingAgentRuns.value = true
  try {
    const response = await $fetch<{ runs: AgentRunTimelineItem[] }>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/agent-runs?limit=8`,
      { headers: protectedHeaders() }
    )
    agentRuns.value = normalizeAgentRuns(response)
  } catch {
    agentRuns.value = []
  } finally {
    loadingAgentRuns.value = false
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

async function loadMentorState() {
  try {
    mentorState.value = await $fetch<ChapterMentorState>(
      `${config.public.apiBaseUrl}/chapters/${chapterId.value}/mentor-state`,
      { headers: protectedHeaders() }
    )
  } catch {
    mentorState.value = null
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

async function runChapterSummary() {
  updatingMentorState.value = true
  mentorErrorMessage.value = ''
  try {
    mentorState.value = await $fetch<ChapterMentorState>(
      `${config.public.apiBaseUrl}/agents/chapter-summary/run`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { chapter_id: chapterId.value }
      }
    )
  } catch (error) {
    mentorErrorMessage.value = appendBackendMessage('Failed to update chapter mentor state.', error)
  } finally {
    updatingMentorState.value = false
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

async function updatePlannerAction(action: PlannerAction, status: string) {
  updatingPlannerActionId.value = action.id
  errorMessage.value = ''
  try {
    const updatedAction = await $fetch<PlannerAction>(
      `${config.public.apiBaseUrl}/planner-actions/${action.id}/status`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { status }
      }
    )
    plannerActions.value = plannerActions.value.map(existingAction =>
      existingAction.id === updatedAction.id ? updatedAction : existingAction
    )
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to update planner action.', error)
  } finally {
    updatingPlannerActionId.value = null
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
  loadMentorState()
  loadMastery()
  loadAgentRuns()
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

      <section class="card chapter-state-panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Chapter state</p>
            <h2>Mentor assessment</h2>
          </div>
          <button
            data-testid="run-chapter-summary"
            class="secondary-button"
            type="button"
            :disabled="updatingMentorState"
            @click="runChapterSummary"
          >
            {{ updatingMentorState ? 'Updating...' : 'Update assessment' }}
          </button>
        </div>

        <template v-if="hasMentorState && mentorState">
          <p v-if="mentorState.summary" class="state-summary">{{ mentorState.summary }}</p>

          <div class="state-grid">
            <section class="state-column">
              <h3>Weak points</h3>
              <ul v-if="mentorState.weak_points?.length" class="state-list">
                <li v-for="point in mentorState.weak_points" :key="point">{{ point }}</li>
              </ul>
              <p v-else class="empty-state">No weak points found.</p>
            </section>

            <section class="state-column">
              <h3>Next actions</h3>
              <ul v-if="mentorState.next_actions?.length" class="state-list">
                <li v-for="action in mentorState.next_actions" :key="action">{{ action }}</li>
              </ul>
              <p v-else class="empty-state">No next actions yet.</p>
            </section>
          </div>

          <dl class="state-meta">
            <div>
              <dt>Sessions</dt>
              <dd>{{ mentorState.source_session_count ?? 0 }}</dd>
            </div>
            <div>
              <dt>Messages</dt>
              <dd>{{ mentorState.source_message_count ?? 0 }}</dd>
            </div>
          </dl>
        </template>

        <p v-else class="empty-state">
          No chapter mentor state yet. Update after asking the mentor a few questions.
        </p>
      </section>

      <section class="card chapter-runtime-panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Chapter runtime</p>
            <h2>Recent agent runs</h2>
            <p class="muted">Latest L2 Mentor and L3 Tutor traces for this chapter.</p>
          </div>
          <button
            data-testid="refresh-chapter-agent-runs"
            class="secondary-button"
            type="button"
            :disabled="loadingAgentRuns"
            @click="loadAgentRuns"
          >
            Refresh
          </button>
        </div>

        <p v-if="loadingAgentRuns" class="muted">Loading runtime...</p>
        <p v-else-if="agentRuns.length === 0" class="empty-state">No chapter runtime yet.</p>
        <div v-else class="chapter-runtime-list">
          <article
            v-for="run in agentRuns"
            :key="run.id ?? `${run.agent_type}-${run.thread_id}`"
            class="chapter-runtime-row"
          >
            <div class="chapter-runtime-meta">
              <span class="status-badge">{{ agentTypeLabel(run.agent_type) }}</span>
              <span class="runtime-status">{{ run.status }}</span>
            </div>
            <div class="chapter-runtime-body">
              <h3>{{ run.summary }}</h3>
              <p v-if="run.node_trace.length" class="runtime-trace">{{ run.node_trace.join(' -> ') }}</p>
              <p v-else class="runtime-trace">No node trace recorded.</p>
              <div v-if="run.learning_signals.length" class="signal-list" aria-label="Learning signals">
                <span
                  v-for="signal in run.learning_signals"
                  :key="signal.kind"
                  class="signal-chip"
                >
                  {{ signal.kind }}
                </span>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="card quiz-panel">
        <div class="section-heading quiz-heading">
          <div>
            <p class="eyebrow">Quiz</p>
            <h2>Check understanding</h2>
          </div>
          <span class="mastery-badge">{{ masteryLabel }}</span>
        </div>

        <div class="quiz-content">
          <p v-if="quizWeakPoint" class="quiz-prompt">
            Focus this quiz on the current weak point: <strong>{{ quizWeakPoint }}</strong>
          </p>
          <p v-else class="quiz-prompt">
            Generate a short check-in quiz for this chapter when you are ready to test recall.
          </p>
          <button
            data-testid="generate-quiz"
            class="primary-button quiz-action"
            type="button"
            :disabled="generatingQuiz"
            @click="generateQuiz"
          >
            {{ generatingQuiz ? 'Generating...' : 'Generate quiz' }}
          </button>
        </div>
      </section>

      <section class="card review-callout">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Planner review</p>
            <h2>Queued review actions</h2>
          </div>
          <span v-if="activeReviewActions.length" class="review-count">
            {{ activeReviewActions.length }} queued
          </span>
        </div>

        <p v-if="loadingPlannerActions" class="muted">Loading review actions...</p>
        <div v-else-if="activeReviewActions.length" class="review-action-list">
          <article
            v-for="action in activeReviewActions"
            :key="action.id"
            class="review-action-row"
          >
            <div class="review-action-copy">
              <div class="review-action-title">
                <h3>{{ action.title }}</h3>
                <span class="status-badge">{{ action.status }}</span>
              </div>
              <p>{{ action.rationale }}</p>
            </div>
            <div class="review-action-buttons">
              <button
                v-if="action.status === 'proposed'"
                data-testid="accept-review-action"
                class="primary-button"
                type="button"
                :disabled="updatingPlannerActionId === action.id"
                @click="updatePlannerAction(action, 'accepted')"
              >
                Accept
              </button>
              <button
                v-if="action.status !== 'completed'"
                class="secondary-button"
                type="button"
                :disabled="updatingPlannerActionId === action.id"
                @click="updatePlannerAction(action, 'completed')"
              >
                Complete
              </button>
              <button
                v-if="action.status === 'proposed'"
                class="secondary-button"
                type="button"
                :disabled="updatingPlannerActionId === action.id"
                @click="updatePlannerAction(action, 'dismissed')"
              >
                Dismiss
              </button>
            </div>
          </article>
        </div>
        <p v-else class="empty-state">No queued review actions for this chapter.</p>
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
.chapter-state-panel,
.chapter-runtime-panel,
.quiz-panel,
.review-callout,
.evidence-panel,
.mentor-panel {
  display: grid;
  gap: 16px;
}

.quiz-panel {
  border-color: rgba(20, 184, 166, 0.22);
  background:
    linear-gradient(135deg, rgba(20, 184, 166, 0.1), rgba(240, 253, 250, 0.64)),
    var(--color-card);
}

.quiz-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.quiz-prompt {
  min-width: 0;
  margin: 0;
  color: var(--color-text);
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.quiz-prompt strong {
  color: var(--color-primary);
  overflow-wrap: anywhere;
}

.mastery-badge {
  border: 1px solid rgba(20, 184, 166, 0.24);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.74);
  color: var(--color-primary);
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 800;
}

.quiz-action {
  flex: 0 0 auto;
}

.chapter-runtime-list {
  display: grid;
  gap: 12px;
}

.chapter-runtime-row {
  display: grid;
  grid-template-columns: minmax(124px, 0.24fr) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  border: 1px solid rgba(20, 184, 166, 0.28);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: 0 10px 26px rgba(15, 118, 110, 0.08);
  min-width: 0;
  padding: 13px;
}

.chapter-runtime-meta,
.chapter-runtime-body {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.chapter-runtime-body h3 {
  color: var(--color-text);
  font-size: 16px;
  line-height: 1.35;
  margin: 0;
  overflow-wrap: anywhere;
}

.runtime-status {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.runtime-trace {
  border-left: 3px solid var(--color-primary-bright);
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  overflow-wrap: anywhere;
  padding-left: 10px;
}

.signal-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.signal-chip {
  border: 1px solid rgba(20, 184, 166, 0.28);
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
  max-width: 100%;
  overflow-wrap: anywhere;
  padding: 6px 8px;
}

.review-callout {
  border-color: rgba(20, 184, 166, 0.24);
  background:
    linear-gradient(135deg, rgba(204, 251, 241, 0.46), rgba(255, 255, 255, 0.82)),
    var(--color-card);
}

.review-count {
  border-radius: 999px;
  padding: 5px 8px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
}

.review-action-list {
  display: grid;
  gap: 12px;
}

.review-action-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  border: 1px solid rgba(20, 184, 166, 0.2);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.76);
  padding: 14px;
}

.review-action-copy {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.review-action-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.review-action-title h3 {
  margin: 0;
  color: var(--color-text);
  font-size: 15px;
  overflow-wrap: anywhere;
}

.review-action-copy p {
  margin: 0;
  color: var(--color-muted);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.review-action-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.state-summary {
  color: var(--color-text);
  font-size: 16px;
  line-height: 1.6;
}

.state-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.state-column {
  display: grid;
  align-content: start;
  gap: 10px;
}

.state-column h3 {
  margin: 0;
  color: var(--color-text);
  font-size: 14px;
}

.state-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 18px;
  color: var(--color-text);
}

.state-list li::marker {
  color: var(--color-primary);
}

.state-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 0;
}

.state-meta div {
  border: 1px solid rgba(20, 184, 166, 0.18);
  border-radius: 8px;
  background: var(--color-primary-soft);
  padding: 8px 10px;
}

.state-meta dt {
  color: var(--color-muted);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.state-meta dd {
  margin: 2px 0 0;
  color: var(--color-primary);
  font-weight: 800;
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
  .summary-grid,
  .state-grid {
    grid-template-columns: 1fr;
  }

  .chapter-heading,
  .chapter-actions,
  .section-heading,
  .evidence-header,
  .quiz-content,
  .review-action-title {
    align-items: stretch;
    flex-direction: column;
  }

  .review-action-row {
    grid-template-columns: 1fr;
  }

  .chapter-runtime-row {
    grid-template-columns: 1fr;
  }

  .review-action-buttons {
    justify-content: stretch;
  }

  .review-action-buttons button {
    flex: 1 1 120px;
  }

  .mentor-panel {
    position: static;
  }
}
</style>
