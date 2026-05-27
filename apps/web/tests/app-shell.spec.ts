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
  it('renders the fresh teal workspace shell', () => {
    const wrapper = mountShell()

    expect(wrapper.text()).toContain('study_agent')
    expect(wrapper.text()).toContain('Spaces')
    expect(wrapper.text()).toContain('Library')
    expect(wrapper.text()).toContain('Reviews')
    expect(wrapper.text()).toContain('Progress')
    expect(wrapper.text()).toContain('Settings')
    expect(wrapper.text()).toContain('Search learning materials')
    expect(wrapper.text()).toContain('Model Ready')
    expect(wrapper.find('[data-testid="page-slot"]').exists()).toBe(true)
  })

  it('loads the shared shell class names used by the design system', () => {
    const wrapper = mountShell()

    expect(wrapper.find('.app-shell').exists()).toBe(true)
    expect(wrapper.find('.sidebar').exists()).toBe(true)
    expect(wrapper.find('.primary-button').exists()).toBe(false)
    expect(wrapper.find('.runtime-pill').text()).toBe('Model Ready')
  })
})
