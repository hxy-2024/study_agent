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

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('Chapter planner review diagnostics', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith(`/chapters/${chapterId}/sessions`)) {
        return Promise.resolve([])
      }
      if (url.endsWith(`/chapters/${chapterId}/annotations`)) {
        return Promise.resolve({ annotations: [] })
      }
      if (url.endsWith(`/chapters/${chapterId}`)) {
        return Promise.resolve(chapterDetail())
      }
      return Promise.resolve({})
    })
  })

  it('does not expose planner action queues in the chat learning interface', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('AI Mentor')
    expect(wrapper.text()).toContain('Progress')
    expect(wrapper.text()).not.toContain('Planner review')
    expect(wrapper.text()).not.toContain('Queued review actions')
    expect(wrapper.find('[data-testid="accept-review-action"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="create-chapter-runtime-actions"]').exists()).toBe(false)
  })
})
