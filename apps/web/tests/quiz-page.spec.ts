import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const quizId = '00000000-0000-0000-0000-000000000A01'
const chapterId = '00000000-0000-0000-0000-000000000601'

vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRoute', () => ({
  params: {
    id: quizId
  }
}))

const { default: QuizPage } = await import('../pages/quizzes/[id].vue')

function mountPage() {
  return mount(QuizPage, {
    global: {
      stubs: {
        NuxtLink: true
      }
    }
  })
}

function quizDetail() {
  return {
    id: quizId,
    study_space_id: '00000000-0000-0000-0000-000000000101',
    chapter_id: chapterId,
    title: 'Retrieval Quiz',
    status: 'active',
    generation_strategy: 'deterministic',
    question_count: 2,
    questions: [
      {
        id: '00000000-0000-0000-0000-000000000B01',
        order_index: 1,
        prompt: 'Which option is grounded in retrieval evidence?',
        options: ['Embedding lookup', 'Unrelated guess', 'Raw prompt only'],
        evidence: {
          source_filename: 'rag.md',
          chunk_index: 2,
          text: 'Retrieval augments generation with source chunks.'
        }
      },
      {
        id: '00000000-0000-0000-0000-000000000B02',
        order_index: 2,
        prompt: 'What should explanations cite?',
        options: ['The linked source text', 'Only the model name', 'A hidden answer key'],
        evidence: {
          source_filename: 'grounding.md',
          chunk_index: 4,
          text: 'Answers should stay grounded in the supplied evidence.'
        }
      },
      {
        id: '00000000-0000-0000-0000-000000000B03',
        order_index: 3,
        prompt: 'What if no evidence is attached?',
        options: ['Continue with the quiz', 'Show an empty evidence card', 'Fail the page'],
        evidence: {
          source_filename: null,
          chunk_index: null,
          text: null
        }
      }
    ]
  }
}

function submissionResult() {
  return {
    id: '00000000-0000-0000-0000-000000000C01',
    quiz_id: quizId,
    chapter_id: chapterId,
    user_id: '00000000-0000-0000-0000-000000000002',
    answers: [0, 1],
    score_percent: 50,
    correct_count: 1,
    question_count: 2,
    results: [
      {
        question_id: '00000000-0000-0000-0000-000000000B01',
        order_index: 1,
        prompt: 'Which option is grounded in retrieval evidence?',
        selected_option_index: 0,
        correct_option_index: 0,
        is_correct: true,
        explanation: 'Embedding lookup is grounded by the source chunk.',
        evidence: {
          source_filename: 'rag.md',
          chunk_index: 2,
          text: 'Retrieval augments generation with source chunks.'
        }
      },
      {
        question_id: '00000000-0000-0000-0000-000000000B02',
        order_index: 2,
        prompt: 'What should explanations cite?',
        selected_option_index: 1,
        correct_option_index: 0,
        is_correct: false,
        explanation: 'Explanations should cite the linked source text.',
        evidence: {
          source_filename: 'grounding.md',
          chunk_index: 4,
          text: 'Answers should stay grounded in the supplied evidence.'
        }
      }
    ],
    weak_points: ['Ground explanations in source evidence'],
    mastery: {
      id: '00000000-0000-0000-0000-000000000D01',
      study_space_id: '00000000-0000-0000-0000-000000000101',
      chapter_id: chapterId,
      score_percent: 50,
      level: 'developing',
      weak_points: ['Ground explanations in source evidence'],
      last_quiz_submission_id: '00000000-0000-0000-0000-000000000C01',
      updated_at: '2026-05-27T10:00:00Z'
    }
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('QuizPage', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith(`/quizzes/${quizId}/submit`) && options?.method === 'POST') {
        return Promise.resolve(submissionResult())
      }
      if (url.endsWith(`/quizzes/${quizId}`)) {
        return Promise.resolve(quizDetail())
      }
      return Promise.resolve({})
    })
  })

  it('loads quiz title, questions, options, and keeps submit disabled until all questions are answered', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/quizzes/${quizId}`,
      expect.objectContaining({ headers: expect.any(Object) })
    )
    expect(wrapper.text()).toContain('Retrieval Quiz')
    expect(wrapper.text()).toContain('Which option is grounded in retrieval evidence?')
    expect(wrapper.text()).toContain('Embedding lookup')
    expect(wrapper.text()).toContain('What should explanations cite?')
    expect(wrapper.text()).toContain('The linked source text')
    expect(wrapper.text()).not.toContain('Embedding lookup is grounded by the source chunk.')

    const submit = wrapper.find('[data-testid="submit-quiz"]')
    expect((submit.element as HTMLButtonElement).disabled).toBe(true)

    await wrapper.find('[data-testid="answer-0-0"]').setValue()
    await wrapper.vm.$nextTick()
    expect((submit.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('submits answers in question order and renders score, explanations, mastery, and weak points', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="answer-1-1"]').setValue()
    await wrapper.find('[data-testid="answer-0-0"]').setValue()
    await wrapper.find('[data-testid="answer-2-0"]').setValue()
    await wrapper.vm.$nextTick()

    const submit = wrapper.find('[data-testid="submit-quiz"]')
    expect((submit.element as HTMLButtonElement).disabled).toBe(false)
    await submit.trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/quizzes/${quizId}/submit`,
      expect.objectContaining({
        method: 'POST',
        body: { answers: [0, 1, 0] }
      })
    )
    expect(wrapper.text()).toContain('50%')
    expect(wrapper.text()).toContain('1 / 2 correct')
    expect(wrapper.text()).toContain('Mastery: developing')
    expect(wrapper.text()).toContain('Ground explanations in source evidence')
    expect(wrapper.text()).toContain('Embedding lookup is grounded by the source chunk.')
    expect(wrapper.text()).toContain('Explanations should cite the linked source text.')
    expect(wrapper.html()).toContain(`/chapters/${chapterId}`)
    expect((submit.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('renders backend evidence DTO fields for questions and result feedback', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('rag.md')
    expect(wrapper.text()).toContain('rag.md / Chunk #2')
    expect(wrapper.text()).toContain('Retrieval augments generation with source chunks.')
    expect(wrapper.text()).not.toContain('Source evidence')

    await wrapper.find('[data-testid="answer-0-0"]').setValue()
    await wrapper.find('[data-testid="answer-1-0"]').setValue()
    await wrapper.find('[data-testid="answer-2-0"]').setValue()
    await wrapper.find('[data-testid="submit-quiz"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('grounding.md')
    expect(wrapper.text()).toContain('grounding.md / Chunk #4')
    expect(wrapper.text()).toContain('Answers should stay grounded in the supplied evidence.')
  })
})
