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
        NuxtLink: {
          props: ['to'],
          template: '<a :href="to"><slot /></a>'
        }
      }
    }
  })
}

function chapterDetail(overrides = {}) {
  const typedOverrides = overrides as {
    chapter?: Record<string, unknown>
    route?: Record<string, unknown>
    study_space?: Record<string, unknown>
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
    evidence: [],
    next_chapter_id: typedOverrides.next_chapter_id ?? null
  }
}

function mentorSession(overrides = {}) {
  return {
    id: '00000000-0000-0000-0000-000000000701',
    chapter_id: '00000000-0000-0000-0000-000000000601',
    title: 'Intro chapter mentor',
    ...overrides
  }
}

function mentorMessage(overrides = {}) {
  return {
    id: '00000000-0000-0000-0000-000000000801',
    session_id: '00000000-0000-0000-0000-000000000701',
    role: 'assistant',
    content: '## Retrieval answer\nRAG retrieves relevant evidence before answering.',
    citations: [
      {
        chunk_id: '00000000-0000-0000-0000-000000000301',
        source_id: '00000000-0000-0000-0000-000000000201',
        source_filename: 'rag.md',
        chunk_index: 2,
        text: 'RAG retrieves relevant evidence.'
      }
    ],
    ...overrides
  }
}

function annotationItem(overrides = {}) {
  return {
    id: '00000000-0000-0000-0000-000000000901',
    tenant_id: '00000000-0000-0000-0000-000000000001',
    user_id: '00000000-0000-0000-0000-000000000002',
    study_space_id: '00000000-0000-0000-0000-000000000101',
    chapter_id: '00000000-0000-0000-0000-000000000601',
    source_chunk_id: null,
    kind: 'note',
    content: 'Remember the vector intuition.',
    quote: null,
    anchor: {},
    created_at: '2026-05-29T00:00:00Z',
    updated_at: '2026-05-29T00:00:00Z',
    ...overrides
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('ChapterStudyPage', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions')) {
        return Promise.resolve([mentorSession()])
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701/messages')) {
        return Promise.resolve([])
      }
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/annotations')) {
        return Promise.resolve({ annotations: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/chapters')) {
        return Promise.resolve({ chapters: [chapterDetail().chapter] })
      }
      return Promise.resolve(chapterDetail())
    })
  })

  it('renders a Codex-style chat workbench instead of diagnostic panels', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Chapters')
    expect(wrapper.text()).toContain('Intro chapter')
    expect(wrapper.text()).toContain('Generate quiz')
    expect(wrapper.text()).toContain('我是你的本章 AI Mentor')
    expect(wrapper.text()).toContain('Sessions')
    expect(wrapper.text()).toContain('Progress')
    expect(wrapper.find('[data-testid="mentor-question"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ask-mentor"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Chapter state')
    expect(wrapper.text()).not.toContain('Chapter runtime')
    expect(wrapper.text()).not.toContain('Source evidence')
    expect(wrapper.text()).not.toContain('Planner review')
  })

  it('renders notes and creates a new chapter note', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string; body?: unknown }) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions')) {
        return Promise.resolve([mentorSession()])
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701/messages')) {
        return Promise.resolve([])
      }
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/annotations') && options?.method === 'POST') {
        return Promise.resolve({ annotation: annotationItem({ content: 'New note' }) })
      }
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/annotations')) {
        return Promise.resolve({ annotations: [annotationItem()] })
      }
      return Promise.resolve(chapterDetail())
    })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Study notes')
    expect(wrapper.text()).toContain('Remember the vector intuition.')

    await wrapper.find('[data-testid="chapter-note-input"]').setValue('New note')
    await wrapper.vm.$nextTick()
    await wrapper.find('form.note-form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/chapters/00000000-0000-0000-0000-000000000601/annotations',
      expect.objectContaining({
        method: 'POST',
        body: { kind: 'note', content: 'New note' }
      })
    )
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

  it('loads existing mentor session messages with markdown and citations', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions')) {
        return Promise.resolve([mentorSession()])
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701/messages')) {
        return Promise.resolve([
          mentorMessage({
            id: '00000000-0000-0000-0000-000000000800',
            role: 'user',
            content: 'How does RAG work?',
            citations: []
          }),
          mentorMessage()
        ])
      }
      return Promise.resolve(chapterDetail())
    })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('How does RAG work?')
    expect(wrapper.text()).toContain('RAG retrieves relevant evidence before answering.')
    expect(wrapper.html()).toContain('<h2>Retrieval answer</h2>')
    expect(wrapper.text()).toContain('rag.md')
    expect(wrapper.text()).toContain('Chunk #2')
    expect(wrapper.text()).toContain('Fork checkpoint')
    expect(wrapper.text()).toContain('Interrupt')
  })

  it('creates a mentor session before sending the first message', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string; body?: unknown }) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions') && options?.method === 'POST') {
        return Promise.resolve(mentorSession())
      }
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions')) {
        return Promise.resolve([])
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701/messages') && options?.method === 'POST') {
        return Promise.resolve(mentorMessage())
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701/messages')) {
        return Promise.resolve([])
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
      'http://localhost:8000/api/v1/chapters/00000000-0000-0000-0000-000000000601/sessions',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sessions/00000000-0000-0000-0000-000000000701/messages',
      expect.objectContaining({
        method: 'POST',
        body: { content: 'How does RAG work?' }
      })
    )
    expect(wrapper.text()).toContain('RAG retrieves relevant evidence before answering.')
  })
})
