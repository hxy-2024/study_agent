import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const navigateToMock = vi.fn()
const spaceId = '00000000-0000-0000-0000-000000000101'
const actionId = '00000000-0000-0000-0000-000000000801'
const chapterId = '00000000-0000-0000-0000-000000000601'
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
    id: spaceId
  }
}))

const { default: StudySpacePage } = await import('../pages/spaces/[id]/index.vue')

function mountPage() {
  return mount(StudySpacePage, {
    global: {
      stubs: {
        NuxtLink: true
      }
    }
  })
}

function activeRoute() {
  return {
    route: {
      id: '00000000-0000-0000-0000-000000000501',
      study_space_id: spaceId,
      version: 1,
      status: 'active',
      title: 'RAG Route',
      summary: 'Learn retrieval and grounded generation.',
      generation_strategy: 'deterministic',
      created_at: null,
      activated_at: null
    },
    chapters: [
      {
        id: chapterId,
        learning_route_id: '00000000-0000-0000-0000-000000000501',
        order_index: 1,
        title: 'Retrieval Basics',
        goal: 'Understand citations.',
        summary: 'Evidence first answers.',
        estimated_days: 2,
        status: 'active',
        source_chunk_refs: []
      }
    ]
  }
}

function plannerState() {
  return {
    id: '00000000-0000-0000-0000-000000000701',
    study_space_id: spaceId,
    summary: 'AI Study: 0/1 chapters complete with 52% average mastery.',
    next_chapter_id: chapterId,
    risk_chapters: [],
    review_recommendations: [],
    route_adjustments: [],
    evidence: [],
    updated_at: null
  }
}

function plannerActions(status = 'proposed') {
  return {
    actions: [
      {
        id: actionId,
        study_space_id: spaceId,
        chapter_id: chapterId,
        source_planner_state_id: '00000000-0000-0000-0000-000000000701',
        action_type: 'review_chapter',
        status,
        title: 'Retake chapter quiz after evidence review.',
        rationale: 'Retrieval Basics: Current mastery is 52%.',
        payload: {},
        created_at: null,
        updated_at: null
      }
    ]
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('StudySpacePage planner actions panel', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    navigateToMock.mockReset()
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith(`/study-spaces/${spaceId}/sources`)) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith(`/study-spaces/${spaceId}/routes`)) {
        return Promise.resolve({ routes: [activeRoute()] })
      }
      if (url.endsWith(`/study-spaces/${spaceId}/planner-state`)) {
        return Promise.resolve(plannerState())
      }
      if (url.endsWith(`/study-spaces/${spaceId}/planner-actions`)) {
        return Promise.resolve(plannerActions())
      }
      if (url.endsWith('/planner-actions/from-latest-state') && options?.method === 'POST') {
        return Promise.resolve(plannerActions())
      }
      if (url.endsWith('/planner-actions/from-runtime-signals') && options?.method === 'POST') {
        return Promise.resolve({
          actions: [
            {
              id: '00000000-0000-0000-0000-000000000802',
              study_space_id: spaceId,
              chapter_id: chapterId,
              source_planner_state_id: null,
              action_type: 'review_chapter',
              status: 'proposed',
              title: 'Review runtime signal evidence.',
              rationale: 'Runtime signals indicate a needed chapter review.',
              payload: { source: 'runtime_signal' },
              created_at: null,
              updated_at: null
            }
          ]
        })
      }
      if (url.endsWith(`/planner-actions/${actionId}/status`) && options?.method === 'POST') {
        return Promise.resolve(plannerActions('accepted').actions[0])
      }
      if (url.endsWith(`/planner-actions/${actionId}/start-review`) && options?.method === 'POST') {
        return Promise.resolve({
          action: plannerActions('accepted').actions[0],
          session: {
            id: sessionId,
            study_space_id: spaceId,
            chapter_id: chapterId,
            title: 'Review: Retake chapter quiz after evidence review.',
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

  it('renders queued planner actions', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Action queue')
    expect(wrapper.text()).toContain('Retake chapter quiz after evidence review.')
    expect(wrapper.text()).toContain('proposed')
  })

  it('creates actions from planner state and accepts an action', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="create-planner-actions"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="accept-planner-action"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/planner-actions/from-latest-state',
      expect.objectContaining({
        method: 'POST',
        body: { study_space_id: spaceId }
      })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/planner-actions/${actionId}/status`,
      expect.objectContaining({
        method: 'POST',
        body: { status: 'accepted' }
      })
    )
    expect(wrapper.text()).toContain('accepted')
  })

  it('creates runtime actions from runtime signals', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="create-runtime-actions"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/planner-actions/from-runtime-signals',
      expect.objectContaining({
        method: 'POST',
        body: { study_space_id: spaceId }
      })
    )
    expect(wrapper.text()).toContain('Review runtime signal evidence.')
  })

  it('starts a focused review from a planner action', async () => {
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
