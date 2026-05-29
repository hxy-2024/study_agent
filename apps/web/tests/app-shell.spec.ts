import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

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
  it('renders the compact top workspace shell', () => {
    const wrapper = mountShell()

    expect(wrapper.text()).toContain('study_agent')
    expect(wrapper.text()).toContain('Local runtime')
    expect(wrapper.find('.hamburger-button').exists()).toBe(true)
    expect(wrapper.find('.avatar-button').text()).toBe('U')
    expect(wrapper.find('[data-testid="page-slot"]').exists()).toBe(true)
  })

  it('opens drawer navigation from the hamburger menu', async () => {
    const wrapper = mountShell()

    expect(wrapper.find('.app-shell').exists()).toBe(true)
    expect(wrapper.find('.nav-drawer').exists()).toBe(false)

    await wrapper.find('.hamburger-button').trigger('click')

    expect(wrapper.find('.nav-drawer').exists()).toBe(true)
    expect(wrapper.text()).toContain('Spaces')
    expect(wrapper.text()).toContain('Library')
    expect(wrapper.text()).toContain('Reviews')
    expect(wrapper.text()).toContain('Progress')
    expect(wrapper.text()).toContain('Settings')
  })

  it('opens local settings from drawer navigation', async () => {
    const wrapper = mountShell()

    await wrapper.find('.hamburger-button').trigger('click')
    await wrapper.findAll('.drawer-nav button').find(button => button.text() === 'Settings')?.trigger('click')

    expect(wrapper.find('.settings-modal').exists()).toBe(true)
    expect(wrapper.text()).toContain('Base URL')
    expect(wrapper.text()).toContain('API key')
    expect(wrapper.text()).toContain('Default model')
    expect(wrapper.text()).toContain('Embedding model')
  })
})
