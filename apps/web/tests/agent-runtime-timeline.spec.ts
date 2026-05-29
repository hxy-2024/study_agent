import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const spaceId = '00000000-0000-0000-0000-000000000101'
const chapterId = '00000000-0000-0000-0000-000000000601'
const sessionId = '00000000-0000-0000-0000-000000000701'
let routeId = spaceId

vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRoute', () => ({
  params: {
    id: routeId
  }
}))

const { default: StudySpacePage } = await import('../pages/spaces/[id]/index.vue')
const { default: ChapterPage } = await import('../pages/chapters/[id]/index.vue')

function mountSpacePage() {
  return mount(StudySpacePage, {
    global: {
      stubs: {
        NuxtLink: true
      }
    }
  })
}

function mountChapterPage() {
  return mount(ChapterPage, {
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

function chapterDetail() {
  return {
    chapter: {
      id: chapterId,
      study_space_id: spaceId,
      learning_route_id: '00000000-0000-0000-0000-000000000501',
      order_index: 1,
      title: 'Retrieval Basics',
      goal: 'Understand citations.',
      summary: 'Evidence first answers.',
      estimated_days: 2,
      status: 'active',
      source_chunk_refs: []
    },
    route: {
      id: '00000000-0000-0000-0000-000000000501',
      study_space_id: spaceId,
      version: 1,
      status: 'active',
      title: 'RAG Route'
    },
    study_space: {
      id: spaceId,
      name: 'AI Study'
    },
    evidence: [],
    next_chapter_id: null
  }
}

function mentorState() {
  return {
    id: '00000000-0000-0000-0000-000000000902',
    chapter_id: chapterId,
    summary: 'Chapter mentor state refreshed.',
    weak_points: ['Citation grounding'],
    next_actions: ['Review retrieved chunks'],
    evidence: [],
    source_session_count: 1,
    source_message_count: 2,
    updated_at: null
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
    routeId = spaceId
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
              graph_name: 'session_tutor',
              checkpoint_backend: 'memory',
              state_schema_version: 1,
              created_at: '2026-05-28T08:00:00.000Z',
              completed_at: '2026-05-28T08:00:00.320Z',
              latency_ms: 320,
              prompt_tokens: 40,
              completion_tokens: 80,
              total_tokens: 120
            }
          ]
        })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
  })

  it('renders recent agent runtime runs', async () => {
    const wrapper = mountSpacePage()
    await flushPromises()

    expect(wrapper.text()).toContain('Agent runtime')
    expect(wrapper.text()).toContain('Session tutor completed with 2 citations.')
    expect(wrapper.text()).toContain('load_session_context')
    expect(wrapper.text()).toContain('weak_point')
  })

  it('expands a runtime row with operational details', async () => {
    const wrapper = mountSpacePage()
    await flushPromises()

    const runtimeButton = wrapper.get('[data-testid="agent-runtime-row-button"]')
    await runtimeButton.trigger('click')

    expect(runtimeButton.attributes('aria-expanded')).toBe('true')
    expect(wrapper.text()).toContain('thread-runtime-1')
    expect(wrapper.text()).toContain('memory')
    expect(wrapper.text()).toContain('Latency')
    expect(wrapper.text()).toContain('Tokens')
  })
})

describe('ChapterPage agent runtime timeline', () => {
  beforeEach(() => {
    routeId = chapterId
    fetchMock.mockReset()
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith(`/chapters/${chapterId}`)) {
        return Promise.resolve(chapterDetail())
      }
      if (url.endsWith(`/chapters/${chapterId}/sessions`)) {
        return Promise.resolve({ sessions: [{ id: sessionId, chapter_id: chapterId, title: 'Runtime mentor' }] })
      }
      if (url.endsWith(`/sessions/${sessionId}/messages`)) {
        return Promise.resolve({ messages: [] })
      }
      if (url.endsWith(`/chapters/${chapterId}/mentor-state`)) {
        return Promise.resolve(mentorState())
      }
      if (url.endsWith(`/chapters/${chapterId}/mastery`)) {
        return Promise.resolve({
          id: '00000000-0000-0000-0000-000000000903',
          chapter_id: chapterId,
          level: 'building',
          score_percent: 66,
          weak_points: ['Citation grounding'],
          updated_at: null
        })
      }
      if (url.endsWith(`/study-spaces/${spaceId}/planner-actions`)) {
        return Promise.resolve({ actions: [] })
      }
      if (url.endsWith(`/chapters/${chapterId}/agent-runs?limit=8`)) {
        return Promise.resolve({
          runs: [
            {
              id: '00000000-0000-0000-0000-000000000904',
              agent_type: 'chapter_mentor',
              status: 'completed',
              summary: 'Chapter mentor state refreshed.',
              node_trace: ['load_chapter_context', 'retrieve_evidence', 'summarize_state'],
              learning_signals: [
                {
                  kind: 'weak_point',
                  label: 'Weak point',
                  value: 'Citation grounding'
                }
              ],
              thread_id: 'thread-runtime-chapter',
              graph_name: 'chapter_mentor',
              checkpoint_backend: 'memory',
              state_schema_version: 1,
              created_at: '2026-05-28T08:05:00.000Z',
              completed_at: '2026-05-28T08:05:00.410Z',
              latency_ms: 410,
              prompt_tokens: 30,
              completion_tokens: 60,
              total_tokens: 90
            },
            {
              id: '00000000-0000-0000-0000-000000000905',
              agent_type: 'session_tutor',
              status: 'completed',
              summary: 'Tutor answered with grounded evidence.',
              node_trace: ['load_session_context', 'retrieve_evidence', 'answer_with_citations'],
              learning_signals: [],
              thread_id: 'thread-runtime-session',
              checkpoint_backend: 'postgres'
            }
          ]
        })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
  })

  it('does not render chapter runtime diagnostics in the chat learning page', async () => {
    const wrapper = mountChapterPage()
    await flushPromises()

    expect(wrapper.text()).toContain('AI Mentor')
    expect(wrapper.text()).toContain('Sessions')
    expect(wrapper.text()).not.toContain('Chapter runtime')
    expect(wrapper.text()).not.toContain('L2 Mentor')
    expect(wrapper.text()).not.toContain('L3 Tutor')
    expect(wrapper.text()).not.toContain('retrieve_evidence')
  })

  it('does not expose expandable runtime rows in the chapter chat page', async () => {
    const wrapper = mountChapterPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="chapter-runtime-row-button"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('thread-runtime-chapter')
    expect(wrapper.text()).not.toContain('Tokens')
  })
})
