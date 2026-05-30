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
  },
  query: {
    source_id: '00000000-0000-0000-0000-000000000201',
    chunk_id: '00000000-0000-0000-0000-000000000301'
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

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('StudySpacePage source jump deep links', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/sources')) {
        return Promise.resolve({
          sources: [
            {
              id: '00000000-0000-0000-0000-000000000201',
              tenant_id: '00000000-0000-0000-0000-000000000001',
              study_space_id: '00000000-0000-0000-0000-000000000101',
              filename: 'rag.md',
              content_type: 'text/markdown',
              object_key: 'tenants/t/spaces/s/sources/source/rag.md',
              status: 'ready',
              error_message: null,
              created_at: '2026-05-27T00:00:00Z'
            }
          ]
        })
      }
      if (url.endsWith('/sources/00000000-0000-0000-0000-000000000201/chunks')) {
        return Promise.resolve({
          chunks: [
            {
              id: '00000000-0000-0000-0000-000000000301',
              source_id: '00000000-0000-0000-0000-000000000201',
              chunk_index: 2,
              text: 'RAG retrieves relevant evidence.',
              citation: { page_number: 4 }
            }
          ]
        })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/routes')) {
        return Promise.resolve({ routes: [] })
      }
      if (url.endsWith('/study-spaces/00000000-0000-0000-0000-000000000101/agent-runs?limit=8')) {
        return Promise.resolve({ runs: [] })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
  })

  it('loads the linked source chunks and highlights the linked chunk', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sources/00000000-0000-0000-0000-000000000201/chunks',
      expect.any(Object)
    )
    expect(wrapper.text()).toContain('rag.md')
    expect(wrapper.text()).toContain('RAG retrieves relevant evidence.')
    const chunk = wrapper.find('[data-testid="source-chunk-00000000-0000-0000-0000-000000000301"]')
    expect(chunk.exists()).toBe(true)
    expect(chunk.classes()).toContain('highlighted')
  })
})
