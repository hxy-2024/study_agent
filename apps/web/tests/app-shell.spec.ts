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

  it('opens local settings from drawer navigation', async () => {
    fetchMock.mockResolvedValueOnce({
      llm_provider: 'openai-compatible',
      llm_base_url: 'https://llm.example.test/v1',
      llm_model: 'study-model',
      llm_api_key_masked: '********',
      web_search_default_enabled: true,
      answer_style: 'socratic'
    })
    const wrapper = mountShell()

    await wrapper.find('.hamburger-button').trigger('click')
    await wrapper.findAll('.drawer-nav button').find(button => button.text() === 'Settings')?.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(wrapper.find('.settings-modal').exists()).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/local-settings/ai')
    expect((wrapper.find('input[type="url"]').element as HTMLInputElement).value).toBe('https://llm.example.test/v1')
    expect(wrapper.text()).toContain('Provider')
    expect(wrapper.text()).toContain('API key')
    expect(wrapper.text()).toContain('Default model')
    expect(wrapper.text()).toContain('Answer style')
  })

  it('saves local AI settings from the settings modal', async () => {
    fetchMock.mockResolvedValueOnce({
      llm_provider: 'deterministic',
      llm_base_url: 'https://api.openai.com/v1',
      llm_model: 'gpt-4.1-mini',
      llm_api_key_masked: '',
      web_search_default_enabled: false,
      answer_style: 'concise'
    })
    fetchMock.mockResolvedValueOnce({
      llm_provider: 'openai-compatible',
      llm_base_url: 'https://llm.example.test/v1',
      llm_model: 'study-model',
      llm_api_key_masked: '********',
      web_search_default_enabled: true,
      answer_style: 'exam_review'
    })
    const wrapper = mountShell()

    await wrapper.find('.hamburger-button').trigger('click')
    await wrapper.findAll('.drawer-nav button').find(button => button.text() === 'Settings')?.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    const inputs = wrapper.findAll('input')
    expect(inputs.length).toBeGreaterThanOrEqual(4)
    await inputs[1]!.setValue('https://llm.example.test/v1')
    await inputs[2]!.setValue('secret-key')
    await inputs[3]!.setValue('study-model')
    await wrapper.find('select').setValue('exam_review')
    await wrapper.find('[data-testid="save-local-settings"]').trigger('click')

    expect(fetchMock).toHaveBeenLastCalledWith('http://127.0.0.1:8000/api/v1/local-settings/ai', {
      method: 'PUT',
      body: {
        llm_provider: 'deterministic',
        llm_base_url: 'https://llm.example.test/v1',
        llm_model: 'study-model',
        llm_api_key: 'secret-key',
        web_search_default_enabled: false,
        answer_style: 'exam_review'
      }
    })
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
