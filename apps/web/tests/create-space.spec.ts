import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRouter', () => ({
  push: vi.fn()
}))

const { default: NewSpacePage } = await import('../pages/spaces/new.vue')

describe('NewSpacePage', () => {
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
})
