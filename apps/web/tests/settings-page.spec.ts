import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()

vi.stubGlobal('$fetch', fetchMock)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://127.0.0.1:8000/api/v1'
  }
}))

const { default: SettingsPage } = await import('../pages/settings.vue')

function localSettings(overrides = {}) {
  return {
    llm_provider: 'deterministic',
    llm_base_url: 'https://api.openai.com/v1',
    llm_model: 'gpt-4.1-mini',
    available_models: [],
    llm_api_key: '',
    llm_api_key_masked: '',
    web_search_default_enabled: false,
    web_search_provider: 'duckduckgo',
    tavily_api_key: '',
    tavily_api_key_masked: '',
    answer_style: 'concise',
    locale: 'zh-CN',
    main_agent_system_prompt: 'Main agent prompt',
    session_tutor_system_prompt: 'Session tutor prompt',
    chapter_mentor_system_prompt: 'Chapter mentor prompt',
    ...overrides
  }
}

describe('Settings page', () => {
  beforeEach(() => {
    fetchMock.mockReset()
  })

  it('loads local settings into categorized panels', async () => {
    fetchMock.mockResolvedValueOnce(localSettings())

    const wrapper = mount(SettingsPage)
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/local-settings/ai', {
      headers: {
        'X-User-Id': '00000000-0000-0000-0000-000000000002',
        'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
      }
    })
    expect(wrapper.text()).toContain('\u8bbe\u7f6e')
    expect(wrapper.text()).toContain('\u5e38\u89c4')
    expect(wrapper.text()).toContain('\u5916\u89c2')
    expect(wrapper.text()).toContain('\u914d\u7f6e')
    expect((wrapper.find('[data-testid="settings-llm-model"]').element as HTMLInputElement).value).toBe('gpt-4.1-mini')
    expect((wrapper.find('[data-testid="settings-api-key"]').element as HTMLInputElement).value).toBe('')
    await wrapper.findAll('.settings-category-button').find(button => button.text() === '\u5916\u89c2')?.trigger('click')
    expect((wrapper.find('[data-testid="settings-locale"]').element as HTMLSelectElement).value).toBe('zh-CN')
    await wrapper.findAll('.settings-category-button').find(button => button.text() === '\u914d\u7f6e')?.trigger('click')
    expect((wrapper.find('[data-testid="settings-main-agent-prompt"]').element as HTMLTextAreaElement).value).toBe('Main agent prompt')
  })

  it('refreshes available models from the configured provider', async () => {
    fetchMock.mockResolvedValueOnce(localSettings({ available_models: ['gpt-4.1-mini'] }))
    fetchMock.mockResolvedValueOnce({
      models: ['deepseek-chat', 'deepseek-reasoner'],
      selected_model: 'deepseek-chat'
    })

    const wrapper = mount(SettingsPage)
    await new Promise(resolve => setTimeout(resolve, 0))

    await wrapper.find('[data-testid="refresh-models"]').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenLastCalledWith('http://127.0.0.1:8000/api/v1/local-settings/ai/models', {
      method: 'POST',
      headers: {
        'X-User-Id': '00000000-0000-0000-0000-000000000002',
        'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
      }
    })
    expect((wrapper.find('[data-testid="settings-llm-model"]').element as HTMLSelectElement).value).toBe('deepseek-chat')
    expect(wrapper.text()).toContain('deepseek-reasoner')
  })

  it('saves language, prompts, answer style, and provider settings', async () => {
    fetchMock.mockResolvedValueOnce(localSettings())
    fetchMock.mockResolvedValueOnce(localSettings({ locale: 'en-US', answer_style: 'code_tutor', llm_api_key: 'secret-key' }))

    const wrapper = mount(SettingsPage)
    await new Promise(resolve => setTimeout(resolve, 0))

    await wrapper.find('[data-testid="settings-provider"]').setValue('openai-compatible')
    await wrapper.find('[data-testid="settings-base-url"]').setValue('https://llm.example.test/v1')
    await wrapper.find('[data-testid="settings-api-key"]').setValue('secret-key')
    await wrapper.findAll('.settings-category-button').find(button => button.text() === '\u5916\u89c2')?.trigger('click')
    await wrapper.find('[data-testid="settings-locale"]').setValue('en-US')
    await wrapper.findAll('.settings-category-button').find(button => button.text() === 'Configuration')?.trigger('click')
    await wrapper.find('[data-testid="settings-answer-style"]').setValue('code_tutor')
    await wrapper.find('[data-testid="settings-main-agent-prompt"]').setValue('Main policy')
    await wrapper.find('[data-testid="settings-session-tutor-prompt"]').setValue('Session policy')
    await wrapper.find('[data-testid="settings-chapter-mentor-prompt"]').setValue('Chapter policy')
    await wrapper.find('[data-testid="save-local-settings"]').trigger('click')

    expect(fetchMock).toHaveBeenLastCalledWith('http://127.0.0.1:8000/api/v1/local-settings/ai', {
      method: 'PUT',
      headers: {
        'X-User-Id': '00000000-0000-0000-0000-000000000002',
        'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
      },
      body: {
        llm_provider: 'openai-compatible',
        llm_base_url: 'https://llm.example.test/v1',
        llm_model: 'gpt-4.1-mini',
        llm_api_key: 'secret-key',
        web_search_default_enabled: false,
        web_search_provider: 'duckduckgo',
        tavily_api_key: '',
        answer_style: 'code_tutor',
        locale: 'en-US',
        main_agent_system_prompt: 'Main policy',
        session_tutor_system_prompt: 'Session policy',
        chapter_mentor_system_prompt: 'Chapter policy'
      }
    })
    expect(wrapper.find('[data-testid="settings-success-toast"]').text()).toBe('Saved')
    expect((wrapper.find('[data-testid="settings-api-key"]').element as HTMLInputElement).value).toBe('secret-key')
  })
})
