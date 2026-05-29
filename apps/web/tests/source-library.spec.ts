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
    id: '00000000-0000-0000-0000-000000000101'
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

function sourceItem(overrides = {}) {
  return {
    id: '00000000-0000-0000-0000-000000000201',
    tenant_id: '00000000-0000-0000-0000-000000000001',
    study_space_id: '00000000-0000-0000-0000-000000000101',
    filename: 'intro.md',
    content_type: 'text/markdown',
    object_key: 'tenants/t/spaces/s/sources/source/intro.md',
    status: 'uploaded',
    error_message: null,
    created_at: '2026-05-27T00:00:00Z',
    ...overrides
  }
}

function sourceListFixture() {
  return [
    sourceItem({
      id: '00000000-0000-0000-0000-000000000201',
      filename: 'uploaded.md',
      status: 'uploaded'
    }),
    sourceItem({
      id: '00000000-0000-0000-0000-000000000202',
      filename: 'ready.md',
      status: 'ready'
    }),
    sourceItem({
      id: '00000000-0000-0000-0000-000000000203',
      filename: 'failed.md',
      status: 'failed',
      error_message: 'Parser failed'
    }),
    sourceItem({
      id: '00000000-0000-0000-0000-000000000204',
      filename: 'processing.md',
      status: 'processing'
    })
  ]
}

function routeItem(overrides = {}) {
  return {
    id: '00000000-0000-0000-0000-000000000501',
    study_space_id: '00000000-0000-0000-0000-000000000101',
    version: 1,
    status: 'draft',
    title: 'Draft route',
    summary: 'A generated route.',
    generation_strategy: 'deterministic',
    created_at: null,
    activated_at: null,
    ...overrides
  }
}

function chapterItem(overrides = {}) {
  return {
    id: '00000000-0000-0000-0000-000000000601',
    learning_route_id: '00000000-0000-0000-0000-000000000501',
    order_index: 1,
    title: 'Intro chapter',
    goal: 'Learn the foundations.',
    summary: 'Start with the basics.',
    estimated_days: 3,
    status: 'not_started',
    source_chunk_refs: [],
    ...overrides
  }
}

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

async function selectFile(wrapper: ReturnType<typeof mountPage>, file: File) {
  const input = wrapper.find<HTMLInputElement>('input[type="file"]')
  Object.defineProperty(input.element, 'files', {
    value: [file],
    configurable: true
  })
  await input.trigger('change')
}

describe('StudySpacePage source library', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/agent-runs?limit=8')) {
        return Promise.resolve({ runs: [] })
      }
      return Promise.resolve({ sources: [] })
    })
  })

  it('renders the source upload control and upload button', async () => {
    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Source library')
    expect(wrapper.find('input[type="file"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Upload source')
  })

  it('renders source rows returned by the API', async () => {
    fetchMock.mockResolvedValueOnce({
      sources: [sourceItem()]
    })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('intro.md')
    expect(wrapper.text()).toContain('Uploaded')
    expect(wrapper.text()).toContain('Run ingestion')
  })

  it('renders the empty chunk preview state', async () => {
    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Chunk preview')
    expect(wrapper.text()).toContain('Select a source to preview parsed chunks.')
  })

  it('rejects unsupported file MIME before calling upload APIs', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await selectFile(wrapper, new File(['%PDF-1.7'], 'notes.pdf', { type: 'application/pdf' }))
    await wrapper.find('button.primary-button').trigger('click')

    expect(wrapper.text()).toContain('This phase supports only .txt and .md files.')
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces/00000000-0000-0000-0000-000000000101/sources',
      expect.any(Object)
    )
  })

  it('rejects a markdown filename when the browser reports an unsupported MIME type', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await selectFile(wrapper, new File(['# Notes'], 'notes.md', { type: 'application/pdf' }))
    await wrapper.find('button.primary-button').trigger('click')

    expect(wrapper.text()).toContain('This phase supports only .txt and .md files.')
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('uploads markdown through presign, storage PUT, confirmation, and source reload', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/agent-runs?limit=8')) {
        return Promise.resolve({ runs: [] })
      }
      if (url.endsWith('/uploads/presign')) {
        return Promise.resolve({
          source_id: '00000000-0000-0000-0000-000000000201',
          object_key: 'tenants/t/spaces/s/sources/source/notes.md',
          upload_url: 'http://object-storage.local/upload/notes.md',
          method: 'PUT'
        })
      }
      if (url === 'http://object-storage.local/upload/notes.md' && options?.method === 'PUT') {
        return Promise.resolve({})
      }
      if (url.endsWith('/sources/00000000-0000-0000-0000-000000000201/uploaded')) {
        return Promise.resolve({})
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const wrapper = mountPage()
    await flushPromises()

    await selectFile(wrapper, new File(['# Notes'], 'notes.md', { type: 'text/markdown' }))
    await wrapper.find('button.primary-button').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenNthCalledWith(4, 'http://localhost:8000/api/v1/uploads/presign', {
      method: 'POST',
      headers: {
        'X-User-Id': '00000000-0000-0000-0000-000000000002',
        'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
      },
      body: {
        study_space_id: '00000000-0000-0000-0000-000000000101',
        filename: 'notes.md',
        content_type: 'text/markdown'
      }
    })
    expect(fetchMock).toHaveBeenNthCalledWith(5, 'http://object-storage.local/upload/notes.md', {
      method: 'PUT',
      headers: {
        'Content-Type': 'text/markdown'
      },
      body: expect.any(File)
    })
    const putHeaders = (fetchMock.mock.calls[4]?.[1] as { headers?: Record<string, string> } | undefined)?.headers
    expect(putHeaders).not.toHaveProperty('X-User-Id')
    expect(putHeaders).not.toHaveProperty('X-Tenant-Id')
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      'http://localhost:8000/api/v1/sources/00000000-0000-0000-0000-000000000201/uploaded',
      {
        method: 'POST',
        headers: {
          'X-User-Id': '00000000-0000-0000-0000-000000000002',
          'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
        }
      }
    )
    expect(fetchMock).toHaveBeenCalledTimes(7)
  })

  it('runs ingestion then loads and renders chunks with citation page', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [sourceItem({ status: options?.method ? 'ready' : 'uploaded' })] })
      }
      if (url.endsWith('/ingestion/sources/00000000-0000-0000-0000-000000000201/run')) {
        return Promise.resolve({})
      }
      if (url.endsWith('/sources/00000000-0000-0000-0000-000000000201/chunks')) {
        return Promise.resolve({
          chunks: [
            {
              id: '00000000-0000-0000-0000-000000000301',
              source_id: '00000000-0000-0000-0000-000000000201',
              chunk_index: 0,
              text: 'Chunk text from markdown',
              citation: { page_number: 1 }
            }
          ]
        })
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button.secondary-button').find(button => button.text() === 'Run ingestion')!.trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/ingestion/sources/00000000-0000-0000-0000-000000000201/run',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sources/00000000-0000-0000-0000-000000000201/chunks',
      expect.any(Object)
    )
    expect(wrapper.text()).toContain('Chunk text from markdown')
    expect(wrapper.text()).toContain('Page 1')
  })

  it.each([
    ['presign', 'http://localhost:8000/api/v1/uploads/presign', 'Failed to create upload URL. Backend says no.'],
    ['storage PUT', 'http://object-storage.local/upload/notes.md', 'Failed to upload file to object storage. Backend says no.'],
    [
      'confirmation',
      'http://localhost:8000/api/v1/sources/00000000-0000-0000-0000-000000000201/uploaded',
      'Failed to confirm upload completion. Backend says no.'
    ]
  ])('shows a specific error when %s fails', async (_phase, failingUrl, expectedMessage) => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/uploads/presign')) {
        if (failingUrl === url) return Promise.reject(new Error('Backend says no.'))
        return Promise.resolve({
          source_id: '00000000-0000-0000-0000-000000000201',
          object_key: 'tenants/t/spaces/s/sources/source/notes.md',
          upload_url: 'http://object-storage.local/upload/notes.md',
          method: 'PUT'
        })
      }
      if (url === 'http://object-storage.local/upload/notes.md') {
        if (failingUrl === url) return Promise.reject(new Error('Backend says no.'))
        return Promise.resolve({})
      }
      if (url.endsWith('/sources/00000000-0000-0000-0000-000000000201/uploaded')) {
        if (failingUrl === url) return Promise.reject(new Error('Backend says no.'))
        return Promise.resolve({})
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const wrapper = mountPage()
    await flushPromises()

    await selectFile(wrapper, new File(['# Notes'], 'notes.md', { type: 'text/markdown' }))
    await wrapper.find('button.primary-button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(expectedMessage)
  })

  it('renders source status filters with counts', async () => {
    fetchMock.mockResolvedValueOnce({ sources: sourceListFixture() })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('All 4')
    expect(wrapper.text()).toContain('Uploaded 1')
    expect(wrapper.text()).toContain('Processing 1')
    expect(wrapper.text()).toContain('Ready 1')
    expect(wrapper.text()).toContain('Failed 1')
  })

  it('filters visible source rows by status', async () => {
    fetchMock.mockResolvedValueOnce({ sources: sourceListFixture() })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-filter="failed"]').trigger('click')

    expect(wrapper.text()).toContain('failed.md')
    expect(wrapper.text()).toContain('Parser failed')
    expect(wrapper.text()).not.toContain('uploaded.md')
    expect(wrapper.text()).not.toContain('ready.md')
  })

  it('shows retry and rerun labels for failed and ready sources', async () => {
    fetchMock.mockResolvedValueOnce({ sources: sourceListFixture() })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Retry ingestion')
    expect(wrapper.text()).toContain('Re-run ingestion')
  })

  it('shows selected file metadata before upload', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await selectFile(wrapper, new File(['# Notes'], 'notes.md', { type: 'text/markdown' }))

    expect(wrapper.text()).toContain('notes.md')
    expect(wrapper.text()).toContain('text/markdown')
    expect(wrapper.text()).toContain('7 B')
  })

  it('shows upload phase text while creating the upload URL', async () => {
    let resolvePresign: (value: unknown) => void = () => {}
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/uploads/presign')) {
        return new Promise(resolve => {
          resolvePresign = resolve
        })
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()
    await selectFile(wrapper, new File(['# Notes'], 'notes.md', { type: 'text/markdown' }))

    await wrapper.find('button.primary-button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Creating upload URL...')

    resolvePresign({
      source_id: '00000000-0000-0000-0000-000000000201',
      object_key: 'tenants/t/spaces/s/sources/source/notes.md',
      upload_url: 'http://object-storage.local/upload/notes.md',
      method: 'PUT'
    })
    await flushPromises()
  })

  it('creates a pasted markdown source and refreshes the source list', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/agent-runs?limit=8')) {
        return Promise.resolve({ runs: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/sources/from-text') && options?.method === 'POST') {
        return Promise.resolve({ source: sourceItem({ filename: 'pasted.md', status: 'uploaded' }) })
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="pasted-source-filename"]').setValue('pasted.md')
    await wrapper.find('[data-testid="pasted-source-content"]').setValue('# Pasted notes')
    await wrapper.find('[data-testid="add-pasted-source"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/api/v1/sources/from-text', {
      method: 'POST',
      headers: {
        'X-User-Id': '00000000-0000-0000-0000-000000000002',
        'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
      },
      body: {
        study_space_id: '00000000-0000-0000-0000-000000000101',
        filename: 'pasted.md',
        content_type: 'text/markdown',
        content: '# Pasted notes'
      }
    })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces/00000000-0000-0000-0000-000000000101/sources',
      expect.any(Object)
    )
  })

  it('keeps the selected file after upload failure', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/uploads/presign')) {
        return Promise.reject(new Error('No upload URL'))
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()
    await selectFile(wrapper, new File(['# Notes'], 'notes.md', { type: 'text/markdown' }))

    await wrapper.find('button.primary-button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('notes.md')
    expect(wrapper.text()).toContain('Failed to create upload URL. No upload URL')
  })

  it('shows preview-level run ingestion action when selected source has no chunks', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [sourceItem({ status: 'uploaded' })] })
      }
      if (url.endsWith('/sources/00000000-0000-0000-0000-000000000201/chunks')) {
        return Promise.resolve({ chunks: [] })
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button.secondary-button').find(button => button.text() === 'View chunks')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('This source has no chunks yet.')
    expect(wrapper.find('[data-testid="preview-run-ingestion"]').exists()).toBe(true)
  })

  it('renders route empty state and generates a draft route', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/route-drafts')) {
        return Promise.resolve({
          route: routeItem({ status: 'draft' }),
          chapters: [chapterItem()]
        })
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('No learning route yet.')

    await wrapper.find('[data-testid="generate-route"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces/00000000-0000-0000-0000-000000000101/route-drafts',
      expect.objectContaining({ method: 'POST' })
    )
    expect(wrapper.text()).toContain('Draft route')
    expect(wrapper.text()).toContain('Intro chapter')
    const studyLink = wrapper.find('[data-testid="study-chapter"]')
    expect(studyLink.exists()).toBe(true)
    expect(studyLink.attributes('to')).toBe('/chapters/00000000-0000-0000-0000-000000000601')
  })

  it('activates a draft route from the route panel', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({
          routes: [
            {
              route: routeItem({ status: 'draft' }),
              chapters: [chapterItem()]
            }
          ]
        })
      }
      if (url.endsWith('/routes/00000000-0000-0000-0000-000000000501/activate')) {
        return Promise.resolve({
          route: routeItem({ status: 'active' }),
          chapters: [chapterItem({ status: 'active' })]
        })
      }
      return Promise.resolve({})
    })

    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="activate-route"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/routes/00000000-0000-0000-0000-000000000501/activate',
      expect.objectContaining({ method: 'POST' })
    )
    expect(wrapper.text()).toContain('Active route')
    expect(wrapper.text()).toContain('Draft route')
  })
})
