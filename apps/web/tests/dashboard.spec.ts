import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const storeState = {
  loading: false,
  spaces: [] as Array<{
    id: string
    name: string
    goal: string
    status: string
    target_days: number
  }>,
  loadSpaces: vi.fn()
}

vi.stubGlobal('useStudySpacesStore', () => storeState)

const { default: DashboardPage } = await import('../pages/index.vue')

function mountPage() {
  return mount(DashboardPage, {
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

describe('DashboardPage', () => {
  beforeEach(() => {
    storeState.loading = false
    storeState.spaces = []
    storeState.loadSpaces.mockReset()
  })

  it('renders an empty continue-learning workspace with create action', () => {
    const wrapper = mountPage()

    expect(wrapper.text()).toContain('Continue Learning')
    expect(wrapper.text()).toContain('Create your first study space')
    expect(wrapper.text()).toContain('New Study Space')
    expect(wrapper.find('a[href="/spaces/new"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('AI Mentor')
    expect(wrapper.text()).toContain('Weekly Progress')
    expect(storeState.loadSpaces).toHaveBeenCalledTimes(1)
  })

  it('renders the most recent space as the primary continue action', () => {
    storeState.spaces = [
      {
        id: 'space-1',
        name: 'Linear Algebra',
        goal: 'Master eigenvectors and matrices',
        status: 'active',
        target_days: 21
      },
      {
        id: 'space-2',
        name: 'Rust Systems',
        goal: 'Build reliable async services',
        status: 'draft',
        target_days: 30
      }
    ]

    const wrapper = mountPage()

    expect(wrapper.text()).toContain('Continue Learning')
    expect(wrapper.text()).toContain('Linear Algebra')
    expect(wrapper.text()).toContain('Master eigenvectors and matrices')
    expect(wrapper.text()).toContain('Continue')
    expect(wrapper.text()).toContain('Recent Spaces')
    expect(wrapper.find('a[href="/spaces/space-1"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('2 active spaces')
  })
})
