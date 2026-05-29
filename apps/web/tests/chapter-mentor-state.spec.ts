import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const chapterId = '00000000-0000-0000-0000-000000000601'

vi.stubGlobal('$fetch', fetchMock)
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

function mentorState(overrides = {}) {
  return {
    id: '00000000-0000-0000-0000-000000000901',
    chapter_id: chapterId,
    summary: 'The learner understands retrieval basics but needs tighter citation habits.',
    weak_points: ['Citation precision'],
    next_actions: ['Review cited chunks'],
    evidence: [{ message_id: '00000000-0000-0000-0000-000000000801' }],
    source_session_count: 2,
    source_message_count: 5,
    updated_at: '2026-05-27T10:00:00Z',
    ...overrides
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('Chapter mentor state panel', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith(`/chapters/${chapterId}/mentor-state`)) {
        return Promise.resolve(mentorState())
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

  it('renders current chapter mentor state', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Chapter state')
    expect(wrapper.text()).toContain('Mentor assessment')
    expect(wrapper.text()).toContain('Citation precision')
    expect(wrapper.text()).toContain('Review cited chunks')
  })

  it('runs chapter summary update', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith('/agents/chapter-summary/run') && options?.method === 'POST') {
        return Promise.resolve(
          mentorState({
            summary: 'Updated mentor assessment.',
            weak_points: ['Evidence linking'],
            next_actions: ['Revisit source notes']
          })
        )
      }
      if (url.endsWith(`/chapters/${chapterId}/mentor-state`)) {
        return Promise.resolve(mentorState())
      }
      if (url.endsWith(`/chapters/${chapterId}/sessions`)) {
        return Promise.resolve([])
      }
      if (url.endsWith(`/chapters/${chapterId}`)) {
        return Promise.resolve(chapterDetail())
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="run-chapter-summary"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/agents/chapter-summary/run',
      expect.objectContaining({
        method: 'POST',
        body: { chapter_id: chapterId }
      })
    )
    expect(wrapper.text()).toContain('Updated mentor assessment.')
  })

  it('shows supervision refresh callout when tutor signals are newer than the mentor state', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith(`/chapters/${chapterId}/mentor-state`)) {
        return Promise.resolve(
          mentorState({
            needs_supervision_refresh: true,
            latest_session_tutor_run_at: '2026-05-27T10:05:00Z'
          })
        )
      }
      if (url.endsWith(`/chapters/${chapterId}/sessions`)) {
        return Promise.resolve([])
      }
      if (url.endsWith(`/chapters/${chapterId}`)) {
        return Promise.resolve(chapterDetail())
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('New tutor signals need assessment')
    expect(wrapper.text()).toContain('Update assessment')
  })

  it('renders empty state when mentor-state request fails', async () => {
    fetchMock.mockImplementation((url: string) => {
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

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain(
      'No chapter mentor state yet. Update after asking the mentor a few questions.'
    )
  })
})
