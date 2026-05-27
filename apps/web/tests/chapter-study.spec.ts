import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()

vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRoute', () => ({
  params: {
    id: '00000000-0000-0000-0000-000000000601'
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

function chapterDetail(overrides = {}) {
  const typedOverrides = overrides as {
    chapter?: Record<string, unknown>
    route?: Record<string, unknown>
    study_space?: Record<string, unknown>
    evidence?: unknown[]
    next_chapter_id?: string | null
  }

  return {
    chapter: {
      id: '00000000-0000-0000-0000-000000000601',
      study_space_id: '00000000-0000-0000-0000-000000000101',
      learning_route_id: '00000000-0000-0000-0000-000000000501',
      order_index: 1,
      title: 'Intro chapter',
      goal: 'Learn the foundations.',
      summary: 'Start with the basics.',
      estimated_days: 3,
      status: 'active',
      source_chunk_refs: [],
      ...typedOverrides.chapter
    },
    route: {
      id: '00000000-0000-0000-0000-000000000501',
      study_space_id: '00000000-0000-0000-0000-000000000101',
      version: 1,
      status: 'active',
      title: 'Draft route',
      ...typedOverrides.route
    },
    study_space: {
      id: '00000000-0000-0000-0000-000000000101',
      name: 'Linear Algebra',
      ...typedOverrides.study_space
    },
    evidence: typedOverrides.evidence ?? [],
    next_chapter_id: typedOverrides.next_chapter_id ?? null
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('ChapterStudyPage', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue(chapterDetail())
  })

  it('renders chapter details and active mentor panel', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Intro chapter')
    expect(wrapper.text()).toContain('Learn the foundations.')
    expect(wrapper.text()).toContain('Start with the basics.')
    expect(wrapper.text()).toContain('Draft route')
    expect(wrapper.text()).toContain('AI Mentor')
    expect(wrapper.find('[data-testid="mentor-question"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ask-mentor"]').exists()).toBe(true)
  })

  it('renders source evidence cards', async () => {
    fetchMock.mockResolvedValueOnce(
      chapterDetail({
        evidence: [
          {
            source_id: '00000000-0000-0000-0000-000000000201',
            chunk_id: '00000000-0000-0000-0000-000000000301',
            chunk_index: 0,
            source_filename: 'notes.md',
            text: 'Embeddings convert text into vectors.',
            citation: { page_number: 2 }
          }
        ]
      })
    )

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('notes.md')
    expect(wrapper.text()).toContain('Embeddings convert text into vectors.')
    expect(wrapper.text()).toContain('Page 2')
  })

  it('renders empty evidence state', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('No source evidence is linked to this chapter yet.')
  })

  it('marks chapter complete and shows next chapter action', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/complete') && options?.method === 'POST') {
        return Promise.resolve(
          chapterDetail({
            chapter: { status: 'completed' },
            next_chapter_id: '00000000-0000-0000-0000-000000000602'
          })
        )
      }
      return Promise.resolve(chapterDetail())
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="complete-chapter"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/chapters/00000000-0000-0000-0000-000000000601/complete',
      expect.objectContaining({ method: 'POST' })
    )
    expect(wrapper.text()).toContain('completed')
    expect(wrapper.html()).toContain('/chapters/00000000-0000-0000-0000-000000000602')
  })

  it('asks the chapter mentor and renders answer citations', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string; body?: unknown }) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/mentor/questions') && options?.method === 'POST') {
        return Promise.resolve({
          question: 'How does RAG work?',
          answer: 'RAG retrieves relevant evidence before answering.',
          citations: [
            {
              chunk_id: '00000000-0000-0000-0000-000000000301',
              source_id: '00000000-0000-0000-0000-000000000201',
              source_filename: 'rag.md',
              chunk_index: 2,
              text: 'RAG retrieves relevant evidence.'
            }
          ]
        })
      }
      return Promise.resolve(chapterDetail())
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="mentor-question"]').setValue('How does RAG work?')
    await wrapper.vm.$nextTick()
    await wrapper.find('form.mentor-form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/chapters/00000000-0000-0000-0000-000000000601/mentor/questions',
      expect.objectContaining({
        method: 'POST',
        body: { question: 'How does RAG work?' }
      })
    )
    expect(wrapper.text()).toContain('RAG retrieves relevant evidence before answering.')
    expect(wrapper.text()).toContain('rag.md')
    expect(wrapper.text()).toContain('Chunk #2')
  })
})
