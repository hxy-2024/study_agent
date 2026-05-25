import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import NewSpacePage from '../pages/spaces/new.vue'

describe('NewSpacePage', () => {
  it('renders the AI render button and submit button', () => {
    const wrapper = mount(NewSpacePage, {
      global: {
        stubs: {
          NuxtLink: true
        }
      }
    })

    expect(wrapper.text()).toContain('AI 渲染')
    expect(wrapper.text()).toContain('创建空间')
  })
})
