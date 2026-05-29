import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
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

vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
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
    fetchMock.mockReset()
    fetchMock.mockRejectedValue(new Error('Dashboard not ready'))
  })

  it('renders an empty continue-learning workspace with create action', () => {
    const wrapper = mountPage()

    expect(wrapper.text()).toContain('Learning dashboard')
    expect(wrapper.text()).toContain('Create your first study space')
    expect(wrapper.text()).toContain('New Study Space')
    expect(wrapper.text()).toContain('Calendar')
    expect(wrapper.text()).toContain('Add diary')
    expect(wrapper.find('a[href="/spaces/new"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('AI Mentor')
    expect(storeState.loadSpaces).toHaveBeenCalledTimes(1)
  })

  it('renders spaces in the left list and selects the newest as the primary continue action', () => {
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

    expect(wrapper.text()).toContain('Learning dashboard')
    expect(wrapper.text()).toContain('Linear Algebra')
    expect(wrapper.text()).toContain('Master eigenvectors and matrices')
    expect(wrapper.text()).toContain('Continue')
    expect(wrapper.find('a[href="/spaces/space-1"]').exists()).toBe(true)
    expect(wrapper.findAll('.space-row')).toHaveLength(2)
    expect(wrapper.find('.space-row.active').text()).toContain('Linear Algebra')
  })

  it('filters spaces by search text', async () => {
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
    await wrapper.find('input[type="search"]').setValue('rust')

    expect(wrapper.findAll('.space-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('Rust Systems')
    expect(wrapper.text()).not.toContain('Master eigenvectors and matrices')
  })

  it('renders local dashboard summary metrics when available', async () => {
    fetchMock.mockResolvedValue({
      spaces: [
        {
          id: 'space-1',
          name: 'Linear Algebra',
          goal: 'Master eigenvectors and matrices',
          status: 'active',
          target_days: 21
        }
      ],
      pending_actions: [
        {
          id: 'action-1',
          study_space_id: 'space-1',
          chapter_id: 'chapter-1',
          title: 'Review Retrieval',
          status: 'proposed'
        }
      ],
      supervision_refresh_count: 2,
      recent_agent_runs: [
        {
          id: 'run-1',
          agent_type: 'session_tutor',
          status: 'completed',
          summary: 'Tutor answered with citations.'
        }
      ]
    })

    const wrapper = mountPage()
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(wrapper.text()).toContain('Today')
    expect(wrapper.text()).toContain('1 pending action')
    expect(wrapper.text()).toContain('2 supervision refreshes')
    expect(wrapper.text()).toContain('Tutor answered with citations.')
  })
})
