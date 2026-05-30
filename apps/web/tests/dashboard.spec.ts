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

async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0))
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
    expect(wrapper.text()).toContain('Prepare route')
    expect(wrapper.find('a[href="/spaces/new"]').exists()).toBe(true)
    expect(wrapper.findAll('.space-row')).toHaveLength(2)
    expect(wrapper.find('.space-row.active').text()).toContain('Linear Algebra')
  })

  it('continues an existing study space directly into its chapter chat', async () => {
    storeState.spaces = [
      {
        id: 'space-1',
        name: 'Linear Algebra',
        goal: 'Master eigenvectors and matrices',
        status: 'active',
        target_days: 21
      }
    ]
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/space-1/chapters')) {
        return Promise.resolve({
          chapters: [
            {
              id: 'chapter-1',
              status: 'active',
              order_index: 1
            }
          ]
        })
      }
      return Promise.reject(new Error('Dashboard not ready'))
    })

    const wrapper = mountPage()
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('Continue study')
    expect(wrapper.find('a[href="/chapters/chapter-1"]').exists()).toBe(true)
  })

  it('falls back to route drafts when active chapters are not listed yet', async () => {
    storeState.spaces = [
      {
        id: 'space-1',
        name: 'Linear Algebra',
        goal: 'Master eigenvectors and matrices',
        status: 'active',
        target_days: 21
      }
    ]
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces/space-1/chapters')) {
        return Promise.resolve({ chapters: [] })
      }
      if (url.endsWith('/study-spaces/space-1/routes')) {
        return Promise.resolve({
          routes: [
            {
              route: {
                id: 'route-1',
                status: 'draft'
              },
              chapters: [
                {
                  id: 'chapter-draft-1',
                  status: 'active',
                  order_index: 1
                }
              ]
            }
          ]
        })
      }
      return Promise.reject(new Error('Dashboard not ready'))
    })

    const wrapper = mountPage()
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('Continue study')
    expect(wrapper.find('.space-row a[href="/chapters/chapter-draft-1"]').exists()).toBe(true)
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
    await flushPromises()

    expect(wrapper.text()).toContain('Today')
    expect(wrapper.text()).toContain('1 pending action')
    expect(wrapper.text()).toContain('2 supervision refreshes')
    expect(wrapper.text()).toContain('Tutor answered with citations.')
    expect(wrapper.text()).toContain('Continue study')
    expect(wrapper.find('a[href="/chapters/chapter-1"]').exists()).toBe(true)
  })

  it('renders the main agent today recommendation as the primary action', async () => {
    fetchMock.mockResolvedValue({
      spaces: [
        {
          id: 'space-1',
          name: 'RAG Basics',
          goal: 'Learn retrieval',
          status: 'active',
          target_days: 14
        }
      ],
      pending_actions: [],
      supervision_refresh_count: 0,
      recent_agent_runs: [],
      today_recommendation: {
        agent_type: 'main_agent',
        title: 'Continue Retrieval',
        action_label: 'Study now',
        action_url: '/chapters/chapter-1',
        recommendation_type: 'continue_chapter',
        reason: 'RAG Basics has an unfinished chapter ready.',
        estimated_minutes: 25,
        study_space_id: 'space-1',
        chapter_id: 'chapter-1',
        freshness: 'deterministic_fallback',
        secondary_actions: [
          {
            title: 'Review citations',
            action_label: 'Review',
            action_url: '/chapters/chapter-2',
            recommendation_type: 'review_chapter',
            reason: 'Your last quiz showed citation uncertainty.'
          }
        ]
      }
    })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Main Agent')
    expect(wrapper.text()).toContain('Continue Retrieval')
    expect(wrapper.text()).toContain('RAG Basics has an unfinished chapter ready.')
    expect(wrapper.find('a[href="/chapters/chapter-1"]').text()).toContain('Study now')
    expect(wrapper.text()).toContain('Review citations')
  })

  it('shows archived spaces and restores one from the dashboard', async () => {
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url.endsWith('/dashboard')) {
        return Promise.resolve({
          spaces: [],
          pending_actions: [],
          supervision_refresh_count: 0,
          recent_agent_runs: []
        })
      }
      if (url.endsWith('/study-spaces/archived')) {
        return Promise.resolve([
          {
            id: 'space-archived',
            name: 'Archived RAG',
            goal: 'Old retrieval notes',
            status: 'archived',
            target_days: 14
          }
        ])
      }
      if (url.endsWith('/study-spaces/space-archived/restore') && options?.method === 'POST') {
        return Promise.resolve({})
      }
      return Promise.reject(new Error(`Unexpected request ${url}`))
    })

    const wrapper = mountPage()
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('Archived')
    expect(wrapper.text()).toContain('Archived RAG')

    await wrapper.find('[data-testid="restore-space-space-archived"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces/space-archived/restore',
      expect.objectContaining({ method: 'POST' })
    )
    expect(storeState.loadSpaces).toHaveBeenCalledTimes(2)
  })

  it('links the current space export endpoints', () => {
    storeState.spaces = [
      {
        id: 'space-1',
        name: 'Linear Algebra',
        goal: 'Master eigenvectors and matrices',
        status: 'active',
        target_days: 21
      }
    ]

    const wrapper = mountPage()

    expect(wrapper.find('a[href="http://localhost:8000/api/v1/study-spaces/space-1/export"]').exists()).toBe(true)
    expect(wrapper.find('a[href="http://localhost:8000/api/v1/study-spaces/space-1/export?format=markdown"]').exists()).toBe(true)
  })
})
