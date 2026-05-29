import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const navigateToMock = vi.fn()
const chapterId = '00000000-0000-0000-0000-000000000601'
const otherChapterId = '00000000-0000-0000-0000-000000000602'
const spaceId = '00000000-0000-0000-0000-000000000101'
const actionId = '00000000-0000-0000-0000-000000000801'
const sessionId = '00000000-0000-0000-0000-000000000901'

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
      study_space_id: spaceId,
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
      study_space_id: spaceId,
      version: 1,
      status: 'active',
      title: 'Draft route'
    },
    study_space: {
      id: spaceId,
      name: 'Linear Algebra'
    },
    evidence: [],
    next_chapter_id: null
  }
}

function plannerAction(overrides = {}) {
  return {
    id: actionId,
    study_space_id: spaceId,
    chapter_id: chapterId,
    source_planner_state_id: '00000000-0000-0000-0000-000000000701',
    action_type: 'review_chapter',
    status: 'proposed',
    title: 'Review retrieval evidence before continuing.',
    rationale: 'Intro chapter needs another pass.',
    payload: {},
    created_at: null,
    updated_at: null,
    ...overrides
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('Chapter review callout', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    navigateToMock.mockReset()
    fetchMock.mockImplementation((url: string, options?: { method?: string; body?: unknown }) => {
      if (url.endsWith(`/chapters/${chapterId}/mastery`)) {
        return Promise.reject(new Error('Not found'))
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
      if (url.endsWith(`/study-spaces/${spaceId}/planner-actions`)) {
        return Promise.resolve({
          actions: [
            plannerAction(),
            plannerAction({
              id: '00000000-0000-0000-0000-000000000802',
              chapter_id: otherChapterId,
              title: 'Review a different chapter.'
            }),
            plannerAction({
              id: '00000000-0000-0000-0000-000000000803',
              status: 'completed',
              title: 'Already completed review.'
            })
          ]
        })
      }
      if (url.endsWith('/planner-actions/from-runtime-signals') && options?.method === 'POST') {
        return Promise.resolve({
          actions: [
            plannerAction({
              id: '00000000-0000-0000-0000-000000000804',
              title: 'Review runtime signal evidence.',
              rationale: 'Runtime signals indicate the chapter needs another pass.'
            })
          ]
        })
      }
      if (url.endsWith(`/planner-actions/${actionId}/status`) && options?.method === 'POST') {
        return Promise.resolve(plannerAction({ status: 'accepted' }))
      }
      if (url.endsWith(`/planner-actions/${actionId}/start-review`) && options?.method === 'POST') {
        return Promise.resolve({
          action: plannerAction({ status: 'accepted' }),
          session: {
            id: sessionId,
            study_space_id: spaceId,
            chapter_id: chapterId,
            title: 'Review: Review retrieval evidence before continuing.',
            status: 'active',
            summary: null,
            created_at: null,
            updated_at: null
          }
        })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
  })

  it('shows current chapter review actions only', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Planner review')
    expect(wrapper.text()).toContain('Queued review actions')
    expect(wrapper.text()).toContain('Review retrieval evidence before continuing.')
    expect(wrapper.text()).not.toContain('Review a different chapter.')
    expect(wrapper.text()).not.toContain('Already completed review.')
  })

  it('accepts a current chapter review action', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="accept-review-action"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/planner-actions/${actionId}/status`,
      expect.objectContaining({
        method: 'POST',
        body: { status: 'accepted' }
      })
    )
    expect(wrapper.text()).toContain('accepted')
  })

  it('creates runtime actions for the current chapter', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="create-chapter-runtime-actions"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/planner-actions/from-runtime-signals',
      expect.objectContaining({
        method: 'POST',
        body: {
          study_space_id: spaceId,
          chapter_id: chapterId
        }
      })
    )
    expect(wrapper.text()).toContain('Review runtime signal evidence.')
  })

  it('starts a focused review session for the current chapter action', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="start-review-action"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/planner-actions/${actionId}/start-review`,
      expect.objectContaining({
        method: 'POST'
      })
    )
    expect(navigateToMock).toHaveBeenCalledWith(`/chapters/${chapterId}?session_id=${sessionId}`)
  })
})
