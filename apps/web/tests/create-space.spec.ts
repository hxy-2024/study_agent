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

  it('renders the redesigned workspace form and create controls', () => {
    const wrapper = mount(NewSpacePage, {
      global: {
        stubs: {
          NuxtLink: {
            props: ['to'],
            template: '<a :href="to"><slot /></a>'
          }
        }
      }
    })

    expect(wrapper.text()).toContain('Create Study Space')
    expect(wrapper.text()).toContain('Goal')
    expect(wrapper.text()).toContain('Source setup')
    expect(wrapper.text()).toContain('Route preview')
    expect(wrapper.text()).toContain('AI Render')
    expect(wrapper.text()).toContain('Create Space')
  })

  it('creates a study space with auth headers and business fields only', async () => {
    const wrapper = mount(NewSpacePage, {
      global: {
        stubs: {
          NuxtLink: {
            props: ['to'],
            template: '<a :href="to"><slot /></a>'
          }
        }
      }
    })

    await wrapper.find('input').setValue('Linear Algebra')
    await wrapper.find('textarea').setValue('Understand matrices')
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
