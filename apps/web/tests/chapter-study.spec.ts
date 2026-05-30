// @ts-ignore - Vitest runs this in Node; the app tsconfig intentionally omits Node globals.
import { readFileSync } from 'node:fs'
// @ts-ignore - Vitest runs this in Node; the app tsconfig intentionally omits Node globals.
import { join } from 'node:path'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

declare const process: { cwd: () => string }

const fetchMock = vi.fn()
const confirmMock = vi.fn()
const promptMock = vi.fn()

vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('confirm', confirmMock)
vi.stubGlobal('prompt', promptMock)
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
const chapterStudySource = readFileSync(
  join(process.cwd(), 'pages/chapters/[id]/index.vue'),
  'utf8'
)

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
    chapters?: Array<Record<string, unknown>>
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
    chapters: typedOverrides.chapters ?? [],
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
    confirmMock.mockReset()
    promptMock.mockReset()
    confirmMock.mockReturnValue(true)
    promptMock.mockReturnValue('Renamed mentor session')
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
    expect(wrapper.text()).toContain('I am your chapter AI Mentor')
    expect(wrapper.text()).toContain('Sessions')
    expect(wrapper.text()).toContain('Progress')
    expect(wrapper.find('[data-testid="mentor-question"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ask-mentor"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="web-search-toggle"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="web-search-toggle"] svg').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Chapter state')
    expect(wrapper.text()).not.toContain('Chapter runtime')
    expect(wrapper.text()).not.toContain('Source evidence')
    expect(wrapper.text()).not.toContain('Planner review')
  })

  it('keeps the chapter page scrollable on mobile layouts', () => {
    expect(chapterStudySource).toContain(':global(body.chapter-study-page) {\n    overflow: auto;')
    expect(chapterStudySource).toContain('.chat-workspace {\n    height: auto;')
  })

  it('lists every chapter from the current route in the left rail', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/chapters')) {
        return Promise.resolve({ chapters: [chapterDetail().chapter] })
      }
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions')) {
        return Promise.resolve([mentorSession()])
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701/messages')) {
        return Promise.resolve([])
      }
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/annotations')) {
        return Promise.resolve({ annotations: [] })
      }
      return Promise.resolve(
        chapterDetail({
          chapters: [
            chapterDetail().chapter,
            {
              ...chapterDetail().chapter,
              id: '00000000-0000-0000-0000-000000000602',
              order_index: 2,
              title: 'Retrieval chapter',
              status: 'not_started'
            },
            {
              ...chapterDetail().chapter,
              id: '00000000-0000-0000-0000-000000000603',
              order_index: 3,
              title: 'Agent chapter',
              status: 'not_started'
            }
          ]
        })
      )
    })

    const wrapper = mountPage()
    await flushPromises()

    const chapterLinks = wrapper.findAll('.chapter-link')
    expect(chapterLinks).toHaveLength(3)
    expect(wrapper.text()).toContain('Intro chapter')
    expect(wrapper.text()).toContain('Retrieval chapter')
    expect(wrapper.text()).toContain('Agent chapter')
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
    expect(wrapper.find('[aria-label="Fork checkpoint"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Interrupt generation"]').exists()).toBe(false)
  })

  it('turns the send button into an interrupt control while mentor generation is running', async () => {
    let abortWasCalled = false
    fetchMock.mockImplementation((url: string, options?: { method?: string; body?: unknown; signal?: AbortSignal }) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions')) {
        return Promise.resolve([mentorSession()])
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701/messages') && options?.method === 'POST') {
        return new Promise((resolve, reject) => {
          options?.signal?.addEventListener('abort', () => {
            abortWasCalled = true
            const error = new Error('Aborted')
            error.name = 'AbortError'
            reject(error)
          })
        })
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701/messages')) {
        return Promise.resolve([])
      }
      return Promise.resolve(chapterDetail())
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="mentor-question"]').setValue('Continue from here')
    await wrapper.find('form.mentor-form').trigger('submit')
    await wrapper.vm.$nextTick()

    const interruptButton = wrapper.find('[data-testid="ask-mentor"]')
    expect(interruptButton.attributes('aria-label')).toBe('Interrupt generation')
    expect(interruptButton.classes()).toContain('is-stopping')
    expect(interruptButton.find('rect').exists()).toBe(true)

    await interruptButton.trigger('click')
    await flushPromises()

    expect(abortWasCalled).toBe(true)
    expect(wrapper.find('[data-testid="ask-mentor"]').attributes('aria-label')).toBe('Send message')
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
        body: { content: 'How does RAG work?', web_search_enabled: false }
      })
    )
    expect(wrapper.text()).toContain('RAG retrieves relevant evidence before answering.')
  })

  it('sends the explicit web search preference with mentor questions', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string; body?: unknown }) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions')) {
        return Promise.resolve([mentorSession()])
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

    await wrapper.find('[data-testid="web-search-toggle"]').trigger('click')
    await wrapper.find('[data-testid="mentor-question"]').setValue('What changed recently?')
    await wrapper.find('form.mentor-form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sessions/00000000-0000-0000-0000-000000000701/messages',
      expect.objectContaining({
        method: 'POST',
        body: { content: 'What changed recently?', web_search_enabled: true }
      })
    )
  })

  it('asks for confirmation before creating a new mentor session', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="new-mentor-session"]').trigger('click')
    await flushPromises()

    expect(confirmMock).toHaveBeenCalledWith('Create a new mentor session?')
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/chapters/00000000-0000-0000-0000-000000000601/sessions',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('renames a mentor session from the right-click menu', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string; body?: unknown }) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions')) {
        return Promise.resolve([mentorSession({ title: 'Old mentor session' })])
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701') && options?.method === 'PATCH') {
        return Promise.resolve(mentorSession({ title: 'Renamed mentor session' }))
      }
      if (url.endsWith('/sessions/00000000-0000-0000-0000-000000000701/messages')) {
        return Promise.resolve([])
      }
      return Promise.resolve(chapterDetail())
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('.session-list-row').trigger('contextmenu')
    expect(wrapper.find('[data-testid="rename-mentor-session"]').exists()).toBe(true)

    await wrapper.find('[data-testid="rename-mentor-session"]').trigger('click')
    await flushPromises()

    expect(promptMock).toHaveBeenCalledWith('Rename session', 'Old mentor session')
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sessions/00000000-0000-0000-0000-000000000701',
      expect.objectContaining({
        method: 'PATCH',
        body: { title: 'Renamed mentor session' }
      })
    )
    expect(wrapper.text()).toContain('Renamed mentor session')
  })

  it('confirms before deleting a mentor session and selects the next session', async () => {
    const deletedSessionId = '00000000-0000-0000-0000-000000000701'
    const nextSessionId = '00000000-0000-0000-0000-000000000702'
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith('/chapters/00000000-0000-0000-0000-000000000601/sessions')) {
        return Promise.resolve([
          mentorSession({ id: deletedSessionId, title: 'First mentor session' }),
          mentorSession({ id: nextSessionId, title: 'Second mentor session' })
        ])
      }
      if (url.endsWith(`/sessions/${deletedSessionId}`) && options?.method === 'DELETE') {
        return Promise.resolve(null)
      }
      if (url.endsWith(`/sessions/${deletedSessionId}/messages`)) {
        return Promise.resolve([])
      }
      if (url.endsWith(`/sessions/${nextSessionId}/messages`)) {
        return Promise.resolve([mentorMessage({ session_id: nextSessionId, content: 'Next session message' })])
      }
      return Promise.resolve(chapterDetail())
    })

    const wrapper = mountPage()
    await flushPromises()

    const deleteButton = wrapper.find('[aria-label="Delete session First mentor session"]')
    expect(deleteButton.exists()).toBe(true)
    expect(deleteButton.find('svg').exists()).toBe(true)

    await deleteButton.trigger('click')
    await flushPromises()

    expect(confirmMock).toHaveBeenCalledWith('Delete this session and its saved messages?')
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/sessions/${deletedSessionId}`,
      expect.objectContaining({ method: 'DELETE' })
    )
    expect(wrapper.text()).not.toContain('First mentor session')
    expect(wrapper.text()).toContain('Second mentor session')
    expect(wrapper.text()).toContain('Next session message')
  })
})
