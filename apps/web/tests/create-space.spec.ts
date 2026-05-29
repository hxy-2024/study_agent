import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const pushMock = vi.fn()

vi.stubGlobal('$fetch', fetchMock)

vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRouter', () => ({
  push: pushMock
}))

const { default: NewSpacePage } = await import('../pages/spaces/new.vue')

describe('NewSpacePage', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    pushMock.mockReset()
    fetchMock.mockResolvedValue({ id: 'space-1' })
  })

  function mountPage() {
    return mount(NewSpacePage, {
      global: {
        stubs: {
          NuxtLink: {
            props: ['to', 'ariaLabel'],
            template: '<a :href="to" :aria-label="ariaLabel"><slot /></a>'
          }
        }
      }
    })
  }

  it('renders the redesigned workspace form and create controls', () => {
    const wrapper = mountPage()

    expect(wrapper.find('[data-testid="back-home"]').attributes('href')).toBe('/')
    expect(wrapper.text()).toContain('创建学习空间')
    expect(wrapper.text()).toContain('学习空间名字')
    expect(wrapper.text()).toContain('学习主题 / Goal')
    expect(wrapper.text()).toContain('默认模型')
    expect(wrapper.text()).toContain('上传材料 / RAG')
    expect(wrapper.text()).toContain('Embedding model')
    expect(wrapper.text()).toContain('AI Render')
    expect(wrapper.text()).toContain('生成章节学习详情')
    expect(wrapper.text()).toContain('Create Space')
  })

  it('keeps generated chunks hidden until the chunk modal opens', async () => {
    const wrapper = mountPage()

    expect(wrapper.text()).not.toContain('Chunk 01')

    await wrapper.find('[data-testid="open-chunk-modal"]').trigger('click')

    expect(wrapper.find('[data-testid="chunk-modal"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Chunk 01')

    await wrapper.find('[data-testid="close-chunk-modal"]').trigger('click')

    expect(wrapper.find('[data-testid="chunk-modal"]').exists()).toBe(false)
  })

  it('shows loading copy and a chapter detail modal after generating chapter details', async () => {
    const wrapper = mountPage()

    await wrapper.find('[data-testid="generate-chapter-details"]').trigger('click')

    expect(wrapper.text()).toContain('正在生成中，请稍等')

    await new Promise((resolve) => setTimeout(resolve, 20))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="chapter-modal"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('章节列表')
    expect(wrapper.text()).toContain('章节详情')

    await wrapper.find('[data-testid="confirm-chapter-details"]').trigger('click')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces',
      expect.objectContaining({
        method: 'POST'
      })
    )
    expect(pushMock).toHaveBeenCalledWith('/spaces/space-1')
  })

  it('creates a study space with auth headers and business fields only', async () => {
    const wrapper = mountPage()

    await wrapper.find('[name="space-name"]').setValue('Linear Algebra')
    await wrapper.find('[name="learning-goal"]').setValue('Understand matrices')
    await wrapper.find('form').trigger('submit')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'X-User-Id': '00000000-0000-0000-0000-000000000002',
          'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
        },
        body: expect.not.objectContaining({
          tenant_id: expect.any(String),
          owner_user_id: expect.any(String)
        })
      })
    )
    expect(pushMock).toHaveBeenCalledWith('/spaces/space-1')
  })
})
