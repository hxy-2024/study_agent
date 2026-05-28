<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

interface QuizEvidence {
  source_filename?: string | null
  chunk_index?: number | null
  text?: string | null
}

interface QuizQuestion {
  id: string
  order_index: number
  prompt: string
  options: string[]
  evidence?: QuizEvidence
}

interface QuizDetail {
  id: string
  study_space_id: string
  chapter_id: string
  title: string
  status: string
  generation_strategy: string
  question_count: number
  questions: QuizQuestion[]
}

interface MasteryRecord {
  id: string
  study_space_id: string
  chapter_id: string
  score_percent: number
  level: string
  weak_points: string[]
  last_quiz_submission_id: string
  updated_at?: string
}

interface QuizQuestionResult {
  question_id: string
  order_index: number
  prompt: string
  selected_option_index: number
  correct_option_index: number
  is_correct: boolean
  explanation: string
  evidence?: QuizEvidence
}

interface QuizSubmissionResult {
  id: string
  quiz_id: string
  chapter_id: string
  user_id: string
  answers: number[]
  score_percent: number
  correct_count: number
  question_count: number
  results: QuizQuestionResult[]
  weak_points: string[]
  mastery: MasteryRecord
  created_at?: string
}

const DEV_AUTH_HEADERS = {
  'X-User-Id': '00000000-0000-0000-0000-000000000002',
  'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
}

const route = useRoute()
const config = useRuntimeConfig()
const quizId = computed(() => String(route.params.id))

const quiz = ref<QuizDetail | null>(null)
const result = ref<QuizSubmissionResult | null>(null)
const answers = ref<Record<string, number>>({})
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

const questions = computed(() => {
  return [...(quiz.value?.questions ?? [])].sort((a, b) => a.order_index - b.order_index)
})
const answeredCount = computed(() => {
  return questions.value.filter(question => answers.value[question.id] !== undefined).length
})
const allAnswered = computed(() => {
  return questions.value.length > 0 && answeredCount.value === questions.value.length
})
const submitDisabled = computed(() => {
  return !allAnswered.value || submitting.value || Boolean(result.value)
})
const sortedResults = computed(() => {
  return [...(result.value?.results ?? [])].sort((a, b) => a.order_index - b.order_index)
})

function protectedHeaders() {
  return DEV_AUTH_HEADERS
}

function appendBackendMessage(base: string, error: unknown) {
  if (error instanceof Error && error.message) return `${base} ${error.message}`
  return base
}

function selectAnswer(questionId: string, optionIndex: number) {
  if (result.value || submitting.value) return
  answers.value = {
    ...answers.value,
    [questionId]: optionIndex
  }
}

function questionResult(questionId: string) {
  return result.value?.results.find(item => item.question_id === questionId) ?? null
}

function optionMarker(question: QuizQuestion, optionIndex: number) {
  const feedback = questionResult(question.id)
  if (!feedback) return ''
  if (feedback.correct_option_index === optionIndex) return 'Correct answer'
  if (feedback.selected_option_index === optionIndex) return 'Your answer'
  return ''
}

function hasEvidence(evidence?: QuizEvidence) {
  return Boolean(
    evidence?.source_filename ||
      (evidence?.chunk_index !== null && evidence?.chunk_index !== undefined) ||
      evidence?.text
  )
}

function evidenceTitle(evidence?: QuizEvidence) {
  if (!evidence) return 'Evidence'
  const source = evidence.source_filename || 'Source evidence'
  if (evidence.chunk_index === null || evidence.chunk_index === undefined) return source
  return `${source} / Chunk #${evidence.chunk_index}`
}

async function loadQuiz() {
  loading.value = true
  errorMessage.value = ''
  try {
    quiz.value = await $fetch<QuizDetail>(
      `${config.public.apiBaseUrl}/quizzes/${quizId.value}`,
      { headers: protectedHeaders() }
    )
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to load quiz.', error)
  } finally {
    loading.value = false
  }
}

async function submitQuiz() {
  if (!quiz.value || submitDisabled.value) return

  submitting.value = true
  errorMessage.value = ''
  try {
    const orderedAnswers = questions.value.map(question => answers.value[question.id])
    result.value = await $fetch<QuizSubmissionResult>(
      `${config.public.apiBaseUrl}/quizzes/${quizId.value}/submit`,
      {
        method: 'POST',
        headers: protectedHeaders(),
        body: { answers: orderedAnswers }
      }
    )
  } catch (error) {
    errorMessage.value = appendBackendMessage('Failed to submit quiz.', error)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadQuiz()
})
</script>

<template>
  <section class="quiz-page page-enter">
    <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>
    <p v-if="loading" class="muted">Loading quiz...</p>

    <template v-if="quiz">
      <div class="topbar quiz-topbar">
        <div>
          <p class="eyebrow">Quiz / {{ quiz.status }}</p>
          <h1>{{ quiz.title }}</h1>
          <p>{{ answeredCount }} / {{ questions.length }} answered</p>
        </div>
        <NuxtLink class="secondary-button back-link" :to="`/chapters/${quiz.chapter_id}`">
          Back to chapter
        </NuxtLink>
      </div>

      <section v-if="result" class="card result-panel" aria-live="polite">
        <div class="section-heading result-heading">
          <div>
            <p class="eyebrow">Result</p>
            <h2>{{ result.score_percent }}%</h2>
            <p>{{ result.correct_count }} / {{ result.question_count }} correct</p>
          </div>
          <span class="status-badge">Mastery: {{ result.mastery.level }}</span>
        </div>

        <div class="result-grid">
          <section>
            <h3>Weak points</h3>
            <ul v-if="result.weak_points.length" class="compact-list">
              <li v-for="point in result.weak_points" :key="point">{{ point }}</li>
            </ul>
            <p v-else class="empty-state">No weak points from this submission.</p>
          </section>

          <section>
            <h3>Mastery record</h3>
            <p class="mastery-copy">
              {{ result.mastery.level }} at {{ result.mastery.score_percent }}%.
            </p>
          </section>
        </div>
      </section>

      <section class="question-stack">
        <article
          v-for="(question, questionIndex) in questions"
          :key="question.id"
          class="card question-card"
        >
          <div class="question-header">
            <span class="status-badge">Question {{ question.order_index }}</span>
            <span
              v-if="questionResult(question.id)"
              class="feedback-badge"
              :class="{ correct: questionResult(question.id)?.is_correct }"
            >
              {{ questionResult(question.id)?.is_correct ? 'Correct' : 'Review' }}
            </span>
          </div>

          <h2>{{ question.prompt }}</h2>

          <div class="option-list" role="radiogroup" :aria-label="question.prompt">
            <label
              v-for="(option, optionIndex) in question.options"
              :key="option"
              class="option-row"
              :class="{
                selected: answers[question.id] === optionIndex,
                locked: Boolean(result),
                correct: questionResult(question.id)?.correct_option_index === optionIndex,
                missed:
                  questionResult(question.id)?.selected_option_index === optionIndex &&
                  questionResult(question.id)?.is_correct === false
              }"
            >
              <input
                type="radio"
                :name="`question-${question.id}`"
                :value="optionIndex"
                :checked="answers[question.id] === optionIndex"
                :disabled="Boolean(result) || submitting"
                :data-testid="`answer-${questionIndex}-${optionIndex}`"
                @change="selectAnswer(question.id, optionIndex)"
              />
              <span class="option-index">{{ String.fromCharCode(65 + optionIndex) }}</span>
              <span class="option-copy">{{ option }}</span>
              <span v-if="optionMarker(question, optionIndex)" class="option-marker">
                {{ optionMarker(question, optionIndex) }}
              </span>
            </label>
          </div>

          <aside v-if="hasEvidence(question.evidence)" class="evidence-box">
            <strong>{{ evidenceTitle(question.evidence) }}</strong>
            <p v-if="question.evidence?.text">{{ question.evidence.text }}</p>
          </aside>

          <section v-if="questionResult(question.id)" class="feedback-panel">
            <p>{{ questionResult(question.id)?.explanation }}</p>
          </section>
        </article>
      </section>

      <section class="card submit-panel">
        <div>
          <p class="eyebrow">Submit</p>
          <h2>{{ result ? 'Quiz submitted' : 'Ready when every question is answered' }}</h2>
        </div>
        <button
          data-testid="submit-quiz"
          class="primary-button"
          type="button"
          :disabled="submitDisabled"
          @click="submitQuiz"
        >
          {{ result ? 'Submitted' : submitting ? 'Submitting...' : 'Submit quiz' }}
        </button>
      </section>

      <section v-if="result" class="feedback-stack">
        <article
          v-for="item in sortedResults"
          :key="item.question_id"
          class="card feedback-card"
        >
          <div class="question-header">
            <span class="status-badge">Feedback {{ item.order_index }}</span>
            <span class="feedback-badge" :class="{ correct: item.is_correct }">
              {{ item.is_correct ? 'Correct' : 'Needs review' }}
            </span>
          </div>
          <h3>{{ item.prompt }}</h3>
          <p>{{ item.explanation }}</p>
          <aside v-if="hasEvidence(item.evidence)" class="evidence-box">
            <strong>{{ evidenceTitle(item.evidence) }}</strong>
            <p v-if="item.evidence?.text">{{ item.evidence.text }}</p>
          </aside>
        </article>
      </section>
    </template>
  </section>
</template>

<style scoped>
.quiz-page,
.question-stack,
.feedback-stack,
.question-card,
.result-panel {
  display: grid;
  gap: 18px;
}

.quiz-topbar,
.section-heading,
.question-header,
.submit-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.quiz-topbar h1,
.question-card h2,
.submit-panel h2,
.result-heading h2 {
  color: var(--color-text);
  overflow-wrap: anywhere;
}

.quiz-topbar p,
.muted,
.mastery-copy {
  color: var(--color-muted);
}

.back-link {
  text-decoration: none;
}

.result-panel {
  border-color: rgba(20, 184, 166, 0.26);
  background:
    linear-gradient(135deg, rgba(20, 184, 166, 0.1), rgba(240, 253, 250, 0.7)),
    var(--color-card);
}

.result-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 0.45fr);
}

.result-grid h3 {
  margin: 0 0 8px;
  color: var(--color-text);
  font-size: 14px;
}

.compact-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 18px;
  color: var(--color-text);
}

.compact-list li::marker {
  color: var(--color-primary);
}

.question-card {
  align-content: start;
}

.question-card h2 {
  margin: 0;
  font-size: clamp(20px, 2.4vw, 26px);
  line-height: 1.25;
}

.option-list {
  display: grid;
  gap: 10px;
}

.option-row {
  min-height: 58px;
  display: grid;
  grid-template-columns: auto 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-text);
  cursor: pointer;
  padding: 10px 12px;
  transition: background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}

.option-row:hover,
.option-row:focus-within {
  border-color: var(--color-primary-bright);
  background: rgba(236, 253, 245, 0.9);
  box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.1);
}

.option-row.selected {
  border-color: rgba(20, 184, 166, 0.5);
  background: var(--color-primary-soft);
}

.option-row.locked {
  cursor: default;
}

.option-row.correct {
  border-color: rgba(22, 163, 74, 0.42);
  background: #f0fdf4;
}

.option-row.missed {
  border-color: rgba(220, 38, 38, 0.28);
  background: #fff1f2;
}

.option-row input {
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary);
}

.option-index {
  display: inline-grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 8px;
  background: rgba(204, 251, 241, 0.72);
  color: var(--color-primary);
  font-weight: 800;
}

.option-copy {
  min-width: 0;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.option-marker,
.feedback-badge {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 800;
  padding: 5px 8px;
  white-space: nowrap;
}

.feedback-badge {
  border: 1px solid rgba(217, 119, 6, 0.28);
  background: #fffbeb;
  color: var(--color-warning);
}

.feedback-badge.correct {
  border-color: rgba(22, 163, 74, 0.28);
  background: #f0fdf4;
  color: var(--color-success);
}

.evidence-box,
.feedback-panel {
  border: 1px solid rgba(20, 184, 166, 0.18);
  border-radius: 8px;
  background: rgba(236, 253, 245, 0.72);
  padding: 12px;
}

.evidence-box strong {
  color: var(--color-primary);
  font-size: 13px;
}

.evidence-box p,
.feedback-panel p,
.feedback-card p {
  margin: 8px 0 0;
  color: var(--color-text);
  line-height: 1.6;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.feedback-panel {
  background: rgba(255, 255, 255, 0.82);
}

.submit-panel {
  position: sticky;
  bottom: 16px;
  border-color: rgba(20, 184, 166, 0.22);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(16px);
}

.submit-panel h2 {
  margin: 0;
  font-size: 18px;
}

.feedback-card {
  display: grid;
  gap: 12px;
}

.feedback-card h3 {
  margin: 0;
  color: var(--color-text);
  overflow-wrap: anywhere;
}

@media (max-width: 760px) {
  .quiz-topbar,
  .section-heading,
  .submit-panel {
    align-items: stretch;
    flex-direction: column;
  }

  .result-grid {
    grid-template-columns: 1fr;
  }

  .option-row {
    grid-template-columns: auto 32px minmax(0, 1fr);
  }

  .option-marker {
    grid-column: 2 / -1;
    justify-self: start;
    white-space: normal;
  }

  .submit-panel {
    position: static;
  }
}
</style>
