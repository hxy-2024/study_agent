import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const navigateToMock = vi.fn()
const chapterId = '00000000-0000-0000-0000-000000000601'

vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('navigateTo', navigateToMock)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRoute', () => ({
  params: {
    id: chapterId
  }
}))

const { default: ChapterStudyPage } = await import('../pages/chapters/[id]/index.vue')

function mountPage() {
  return mount(ChapterStudyPage, {
    global: {
      stubs: {
        NuxtLink: true
      }
    }
  })
}

function chapterDetail() {
  return {
    chapter: {
      id: chapterId,
      study_space_id: '00000000-0000-0000-0000-000000000101',
      learning_route_id: '00000000-0000-0000-0000-000000000501',
      order_index: 1,
      title: 'Intro chapter',
      goal: 'Learn the foundations.',
      summary: 'Start with the basics.',
      estimated_days: 3,
      status: 'active',
      source_chunk_refs: []
    },
    route: {
      id: '00000000-0000-0000-0000-000000000501',
      study_space_id: '00000000-0000-0000-0000-000000000101',
      version: 1,
      status: 'active',
      title: 'Draft route'
    },
    study_space: {
      id: '00000000-0000-0000-0000-000000000101',
      name: 'Linear Algebra'
    },
    evidence: [],
    next_chapter_id: null
  }
}

function masteryRecord() {
  return {
    id: '00000000-0000-0000-0000-000000000901',
    chapter_id: chapterId,
    level: 'developing',
    score_percent: 67,
    weak_points: ['Matrix inverse conditions'],
    last_quiz_submission_id: '00000000-0000-0000-0000-000000000902',
    updated_at: '2026-05-27T10:00:00Z'
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('Chapter quiz panel', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    navigateToMock.mockReset()
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith(`/chapters/${chapterId}/mastery`)) {
        return Promise.resolve(masteryRecord())
      }
      if (url.endsWith(`/chapters/${chapterId}/quizzes/generate`) && options?.method === 'POST') {
        return Promise.resolve({
          id: '00000000-0000-0000-0000-000000000A01',
          chapter_id: chapterId,
          question_count: 3
        })
      }
      if (url.endsWith(`/chapters/${chapterId}/mentor-state`)) {
        return Promise.reject(new Error('Not found'))
      }
      if (url.endsWith(`/chapters/${chapterId}/sessions`)) {
        return Promise.resolve([])
      }
      if (url.endsWith(`/chapters/${chapterId}`)) {
        return Promise.resolve(chapterDetail())
      }
      return Promise.resolve({})
    })
  })

  it('renders top-right quiz action with current mastery in the session panel', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="generate-quiz"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Generate quiz')
    expect(wrapper.text()).toContain('Mastery: developing 67%')
  })

  it('generates a three question quiz and navigates to it', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="generate-quiz"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/chapters/${chapterId}/quizzes/generate`,
      expect.objectContaining({
        method: 'POST',
        body: { question_count: 3 }
      })
    )
    expect(navigateToMock).toHaveBeenCalledWith('/quizzes/00000000-0000-0000-0000-000000000A01')
  })
})
