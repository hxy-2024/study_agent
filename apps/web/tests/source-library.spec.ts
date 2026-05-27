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
    fetchMock.mockResolvedValue({ sources: [] })
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
    expect(fetchMock).toHaveBeenCalledTimes(1)
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
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('uploads markdown through presign, storage PUT, confirmation, and source reload', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({ sources: [] })
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

    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://localhost:8000/api/v1/uploads/presign', {
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
    expect(fetchMock).toHaveBeenNthCalledWith(3, 'http://object-storage.local/upload/notes.md', {
      method: 'PUT',
      headers: {
        'Content-Type': 'text/markdown'
      },
      body: expect.any(File)
    })
    const putHeaders = (fetchMock.mock.calls[2]?.[1] as { headers?: Record<string, string> } | undefined)?.headers
    expect(putHeaders).not.toHaveProperty('X-User-Id')
    expect(putHeaders).not.toHaveProperty('X-Tenant-Id')
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      'http://localhost:8000/api/v1/sources/00000000-0000-0000-0000-000000000201/uploaded',
      {
        method: 'POST',
        headers: {
          'X-User-Id': '00000000-0000-0000-0000-000000000002',
          'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
        }
      }
    )
    expect(fetchMock).toHaveBeenCalledTimes(5)
  })

  it('runs ingestion then loads and renders chunks with citation page', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
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
})
