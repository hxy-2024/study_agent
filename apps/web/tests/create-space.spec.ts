import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const pushMock = vi.fn()

vi.stubGlobal('$fetch', fetchMock)

vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRouter', () => ({
  push: pushMock
}))

const { default: NewSpacePage } = await import('../pages/spaces/new.vue')

function routeDraft() {
  return {
    chapters: [
      {
        id: 'chapter-1',
        order_index: 1,
        title: 'RAG Fundamentals',
        goal: 'Understand retrieval augmented generation.',
        summary: 'Learn chunking, embeddings, retrieval, and grounded answers.',
        estimated_days: 3
      }
    ]
  }
}

function mountPage() {
  return mount(NewSpacePage, {
    global: {
      stubs: {
        NuxtLink: {
          props: ['to', 'ariaLabel'],
          template: '<a :href="to" :aria-label="ariaLabel"><slot /></a>'
        }
      }
    }
  })
}

async function fillRequiredFields(wrapper: ReturnType<typeof mountPage>) {
  await wrapper.find('[name="space-name"]').setValue('Linear Algebra')
  await wrapper.find('[name="learning-goal"]').setValue('Understand matrices')
  await wrapper.find('textarea[placeholder*="Paste course notes"]').setValue('# RAG\nChunking and retrieval notes.')
}

describe('NewSpacePage', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    pushMock.mockReset()
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/study-spaces')) {
        return Promise.resolve({ id: 'space-1' })
      }
      if (url.endsWith('/sources/from-text')) {
        return Promise.resolve({ source: { id: 'source-1' } })
      }
      if (url.endsWith('/ingestion/sources/source-1/run')) {
        return Promise.resolve({ status: 'completed', chunk_count: 1 })
      }
      if (url.endsWith('/sources/source-1/chunks')) {
        return Promise.resolve({
          chunks: [
            {
              id: 'chunk-1',
              chunk_index: 0,
              text: 'Chunking and retrieval notes.',
              citation: {}
            }
          ]
        })
      }
      if (url.endsWith('/study-spaces/space-1/route-drafts')) {
        return Promise.resolve(routeDraft())
      }
      if (url.endsWith('/local-settings/ai')) {
        return Promise.resolve({
          llm_model: 'deepseek-chat',
          available_models: ['deepseek-chat', 'deepseek-reasoner']
        })
      }
      return Promise.resolve({})
    })
  })

  it('renders the ordered create and RAG workflow', () => {
    const wrapper = mountPage()

    expect(wrapper.find('[data-testid="back-home"]').attributes('href')).toBe('/')
    expect(wrapper.text()).toContain('Create learning space')
    expect(wrapper.text()).toContain('Space and learning goal')
    expect(wrapper.text()).not.toContain('Model input')
    expect(wrapper.text()).not.toContain('Custom model')
    expect(wrapper.text()).toContain('Material and RAG ingestion')
    expect(wrapper.text()).toContain('Embedding preset')
    expect(wrapper.text()).toContain('Local chunk embeddings')
    expect(wrapper.text()).toContain('Learning route outline')
    expect(wrapper.text()).toContain('Generate route')
    expect(wrapper.text()).not.toContain('AI Render')
    expect(wrapper.text()).toContain('Generate chapter study details')
  })

  it('generates a real route draft instead of rendering a local placeholder', async () => {
    const wrapper = mountPage()
    await wrapper.find('[name="space-name"]').setValue('Linear Algebra')
    await wrapper.find('[name="learning-goal"]').setValue('Understand matrices')

    await wrapper.find('[data-testid="generate-route"]').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces/space-1/route-drafts',
      expect.objectContaining({ method: 'POST' })
    )
    expect(wrapper.text()).toContain('RAG Fundamentals')
    expect(wrapper.text()).not.toContain('Clarify the learning goal')
  })

  it('requires the space name and goal before generating a route', async () => {
    const wrapper = mountPage()

    await wrapper.find('[data-testid="generate-route"]').trigger('click')

    expect(fetchMock).not.toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces',
      expect.anything()
    )
    expect(wrapper.text()).toContain('Fill in the space name and learning goal before generating a route.')
  })

  it('lists configured local models as embedding preset options', async () => {
    const wrapper = mountPage()
    await new Promise(resolve => setTimeout(resolve, 0))

    const select = wrapper.find('[data-testid="embedding-preset"]')
    expect(select.exists()).toBe(true)
    expect(wrapper.text()).toContain('Current default model: deepseek-chat')
    expect(wrapper.text()).toContain('deepseek-reasoner')
  })

  it('runs RAG before showing embedded chunks', async () => {
    const wrapper = mountPage()
    await fillRequiredFields(wrapper)

    expect(wrapper.text()).not.toContain('Chunking and retrieval notes.')

    await wrapper.find('[data-testid="run-rag"]').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sources/from-text',
      expect.objectContaining({
        method: 'POST',
        body: expect.objectContaining({
          study_space_id: 'space-1',
          content: '# RAG\nChunking and retrieval notes.'
        })
      })
    )
    expect(wrapper.text()).toContain('RAG Fundamentals')

    await wrapper.find('[data-testid="open-chunk-modal"]').trigger('click')

    expect(wrapper.find('[data-testid="chunk-modal"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Chunking and retrieval notes.')
  })

  it('generates chapter details and enters the first chapter directly', async () => {
    const wrapper = mountPage()
    await fillRequiredFields(wrapper)

    await wrapper.find('form').trigger('submit')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Generating, please wait...')

    await new Promise(resolve => setTimeout(resolve, 20))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="chapter-modal"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Chapters')
    expect(wrapper.text()).toContain('Chapter detail')
    expect(wrapper.text()).toContain('RAG Fundamentals')

    await wrapper.find('[data-testid="confirm-chapter-details"]').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(pushMock).toHaveBeenCalledWith('/chapters/chapter-1')
    expect(pushMock).not.toHaveBeenCalledWith('/spaces/space-1')
  })

  it('does not expose the old study-space middle page as the completion target', async () => {
    const wrapper = mountPage()
    await fillRequiredFields(wrapper)

    await wrapper.find('form').trigger('submit')
    await new Promise(resolve => setTimeout(resolve, 20))
    await wrapper.find('[data-testid="confirm-chapter-details"]').trigger('click')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/study-spaces',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'X-User-Id': '00000000-0000-0000-0000-000000000002',
          'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
        }
      })
    )
    expect(pushMock.mock.calls.flat()).not.toContain('/spaces/space-1')
  })
})
