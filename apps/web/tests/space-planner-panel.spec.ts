import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const spaceId = '00000000-0000-0000-0000-000000000101'
const chapterId = '00000000-0000-0000-0000-000000000601'

vi.stubGlobal('$fetch', fetchMock)
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

function plannerState(summary = 'AI Study: 0/1 chapters complete with 52% average mastery across submitted quizzes.') {
  return {
    id: '00000000-0000-0000-0000-000000000701',
    study_space_id: spaceId,
    summary,
    next_chapter_id: chapterId,
    risk_chapters: [
      {
        chapter_id: chapterId,
        title: 'Retrieval Basics',
        reason: 'Mastery score is 52%, below the review threshold.',
        score_percent: 52
      }
    ],
    review_recommendations: [
      {
        chapter_id: chapterId,
        title: 'Retrieval Basics',
        action: 'Retake chapter quiz after evidence review.',
        reason: 'Current mastery is 52%.'
      }
    ],
    route_adjustments: [
      {
        kind: 'insert_review',
        chapter_id: chapterId,
        title: 'Review before continuing: Retrieval Basics',
        rationale: 'Low mastery suggests adding a focused review checkpoint before new material.'
      }
    ],
    evidence: [
      {
        chapter_id: chapterId,
        title: 'Retrieval Basics',
        needs_supervision_refresh: true,
        latest_session_tutor_run_at: '2026-05-28T05:05:00Z',
        mentor_state_updated_at: '2026-05-28T05:00:00Z'
      }
    ],
    updated_at: '2026-05-28T05:00:00Z'
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('StudySpacePage space planner panel', () => {
  beforeEach(() => {
    fetchMock.mockReset()
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
      if (url.endsWith('/agents/space-planner/run') && options?.method === 'POST') {
        return Promise.resolve(plannerState('Planner refreshed.'))
      }
      throw new Error(`Unexpected request: ${url}`)
    })
  })

  it('renders planner state from the API', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Space planner')
    expect(wrapper.text()).toContain('AI Study: 0/1 chapters complete')
    expect(wrapper.text()).toContain('Recommended next: 1. Retrieval Basics')
    expect(wrapper.text()).toContain('Mastery score is 52%')
    expect(wrapper.text()).toContain('Review before continuing: Retrieval Basics')
    expect(wrapper.text()).toContain('1 chapter needs supervision refresh')
  })

  it('runs the planner and refreshes the panel', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="run-space-planner"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/agents/space-planner/run',
      expect.objectContaining({
        method: 'POST',
        body: { study_space_id: spaceId }
      })
    )
    expect(wrapper.text()).toContain('Planner refreshed.')
  })
})
