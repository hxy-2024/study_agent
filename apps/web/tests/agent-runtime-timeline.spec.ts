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

function plannerState() {
  return {
    id: '00000000-0000-0000-0000-000000000701',
    study_space_id: spaceId,
    summary: 'AI Study: route is active.',
    next_chapter_id: chapterId,
    risk_chapters: [],
    review_recommendations: [],
    route_adjustments: [],
    evidence: [],
    updated_at: null
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('StudySpacePage agent runtime timeline', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockImplementation((url: string) => {
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
        return Promise.resolve({ actions: [] })
      }
      if (url.endsWith(`/study-spaces/${spaceId}/agent-runs?limit=8`)) {
        return Promise.resolve({
          runs: [
            {
              id: '00000000-0000-0000-0000-000000000901',
              agent_type: 'session_tutor',
              status: 'completed',
              summary: 'Session tutor completed with 2 citations.',
              node_trace: ['load_session_context', 'retrieve_evidence', 'answer_with_citations'],
              learning_signals: [
                {
                  kind: 'weak_point',
                  label: 'Weak point',
                  value: 'Citation grounding'
                }
              ],
              thread_id: 'thread-runtime-1',
              checkpoint_backend: 'postgres'
            }
          ]
        })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
  })

  it('renders recent agent runtime runs', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Agent runtime')
    expect(wrapper.text()).toContain('Session tutor completed with 2 citations.')
    expect(wrapper.text()).toContain('load_session_context')
    expect(wrapper.text()).toContain('weak_point')
  })
})
