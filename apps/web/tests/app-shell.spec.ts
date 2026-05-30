import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const navigateToMock = vi.fn()
const fetchMock = vi.fn()

vi.stubGlobal('navigateTo', navigateToMock)
vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://127.0.0.1:8000/api/v1'
  }
}))

const { default: AppShell } = await import('../app.vue')

function mountShell() {
  return mount(AppShell, {
    global: {
      stubs: {
        NuxtLink: {
          props: ['to'],
          template: '<a :href="to"><slot /></a>'
        },
        NuxtPage: {
          template: '<section data-testid="page-slot">Page content</section>'
        }
      }
    }
  })
}

describe('App shell', () => {
  beforeEach(() => {
    navigateToMock.mockReset()
    fetchMock.mockReset()
  })

  it('renders the compact top workspace shell', () => {
    const wrapper = mountShell()

    expect(wrapper.text()).toContain('study_agent')
    expect(wrapper.text()).toContain('Local runtime')
    expect(wrapper.find('.hamburger-button').exists()).toBe(true)
    expect(wrapper.find('.hamburger-button svg').exists()).toBe(true)
    expect(wrapper.find('.avatar-button').text()).toBe('U')
    expect(wrapper.find('[data-testid="page-slot"]').exists()).toBe(true)
  })

  it('opens drawer navigation from the hamburger menu', async () => {
    const wrapper = mountShell()

    expect(wrapper.find('.app-shell').exists()).toBe(true)
    expect(wrapper.find('.nav-drawer').exists()).toBe(false)

    await wrapper.find('.hamburger-button').trigger('click')

    expect(wrapper.find('.nav-drawer').exists()).toBe(true)
    expect(wrapper.text()).toContain('Home')
    expect(wrapper.text()).toContain('Library')
    expect(wrapper.text()).toContain('Reviews')
    expect(wrapper.text()).toContain('Progress')
    expect(wrapper.text()).toContain('Settings')
  })

  it('navigates home from the drawer', async () => {
    const wrapper = mountShell()

    await wrapper.find('.hamburger-button').trigger('click')
    await wrapper.findAll('.drawer-nav button').find(button => button.text() === 'Home')?.trigger('click')

    expect(navigateToMock).toHaveBeenCalledWith('/')
    expect(wrapper.find('.nav-drawer').exists()).toBe(false)
  })

  it('navigates to dedicated settings from drawer navigation', async () => {
    const wrapper = mountShell()

    await wrapper.find('.hamburger-button').trigger('click')
    await wrapper.findAll('.drawer-nav button').find(button => button.text() === 'Settings')?.trigger('click')

    expect(navigateToMock).toHaveBeenCalledWith('/settings')
    expect(wrapper.find('.settings-modal').exists()).toBe(false)
  })

  it('opens runtime status from the topbar pill', async () => {
    fetchMock.mockResolvedValueOnce({
      status: 'ok',
      checks: [
        { name: 'api', status: 'ok', detail: 'API is responding.' },
        { name: 'database', status: 'ok', detail: 'Database query succeeded.' },
        { name: 'object_storage', status: 'ok', detail: 'MinIO bucket is reachable.' },
        { name: 'llm', status: 'warning', detail: 'Deterministic local provider is active.' }
      ]
    })
    const wrapper = mountShell()

    await wrapper.find('[data-testid="runtime-status-button"]').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/runtime/status')
    expect(wrapper.find('.runtime-status-modal').exists()).toBe(true)
    expect(wrapper.text()).toContain('Database query succeeded.')
    expect(wrapper.text()).toContain('Deterministic local provider is active.')
  })
})
