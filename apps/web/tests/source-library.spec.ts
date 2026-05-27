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
      sources: [
        {
          id: '00000000-0000-0000-0000-000000000201',
          tenant_id: '00000000-0000-0000-0000-000000000001',
          study_space_id: '00000000-0000-0000-0000-000000000101',
          filename: 'intro.md',
          content_type: 'text/markdown',
          object_key: 'tenants/t/spaces/s/sources/source/intro.md',
          status: 'uploaded',
          error_message: null,
          created_at: '2026-05-27T00:00:00Z'
        }
      ]
    })

    const wrapper = mountPage()
    await new Promise(resolve => setTimeout(resolve, 0))

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
})
