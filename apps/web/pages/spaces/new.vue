<script setup lang="ts">
import { reactive, ref } from 'vue'

const form = reactive({
  name: '',
  goal: '',
  level: 'beginner',
  intensity: 'normal',
  target_days: 30
})

const routeOutline = ref<Array<{ order: number; title: string; description: string; estimated_days: number }>>([])
const submitting = ref(false)
const errorMessage = ref('')

function renderDraftRoute() {
  const first = Math.max(1, Math.floor(form.target_days / 4))
  const second = Math.max(1, Math.floor(form.target_days / 2))
  const third = Math.max(1, form.target_days - first - second)
  routeOutline.value = [
    {
      order: 1,
      title: '学习目标梳理',
      description: `明确 ${form.goal || '当前目标'} 的学习范围、已有基础和完成标准。`,
      estimated_days: first
    },
    {
      order: 2,
      title: '核心概念学习',
      description: '围绕资料和目标拆解关键概念，建立基础知识结构。',
      estimated_days: second
    },
    {
      order: 3,
      title: '综合复习与测评',
      description: '通过小测、错题和复习卡片检查掌握情况。',
      estimated_days: third
    }
  ]
}

async function createSpace() {
  const config = useRuntimeConfig()
  const router = useRouter()
  submitting.value = true
  errorMessage.value = ''
  try {
    const created = await $fetch<{ id: string }>(`${config.public.apiBaseUrl}/study-spaces`, {
      method: 'POST',
      body: {
        tenant_id: '00000000-0000-0000-0000-000000000001',
        owner_user_id: '00000000-0000-0000-0000-000000000002',
        ...form
      }
    })
    await router.push(`/spaces/${created.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '创建学习空间失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section>
    <div class="topbar">
      <div>
        <h1>新建学习空间</h1>
        <p>填写目标，预览学习路线，然后创建空间。</p>
      </div>
    </div>

    <form class="card" style="display: grid; gap: 16px;" @submit.prevent="createSpace">
      <label>
        空间名称
        <input v-model="form.name" required maxlength="160" style="display: block; width: 100%; margin-top: 6px;">
      </label>
      <label>
        学习目标
        <textarea v-model="form.goal" required rows="5" style="display: block; width: 100%; margin-top: 6px;" />
      </label>
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
        <label>
          基础水平
          <select v-model="form.level" style="display: block; width: 100%; margin-top: 6px;">
            <option value="beginner">入门</option>
            <option value="intermediate">有基础</option>
            <option value="advanced">进阶</option>
          </select>
        </label>
        <label>
          学习强度
          <select v-model="form.intensity" style="display: block; width: 100%; margin-top: 6px;">
            <option value="light">轻量</option>
            <option value="normal">标准</option>
            <option value="intensive">强化</option>
          </select>
        </label>
        <label>
          目标天数
          <input
            v-model.number="form.target_days"
            type="number"
            min="1"
            max="365"
            style="display: block; width: 100%; margin-top: 6px;"
          >
        </label>
      </div>

      <div>
        <button type="button" @click="renderDraftRoute">AI 渲染</button>
      </div>

      <div v-if="routeOutline.length" class="card">
        <h2>路线预览</h2>
        <ol>
          <li v-for="chapter in routeOutline" :key="chapter.order">
            <strong>{{ chapter.title }}</strong>
            <p>{{ chapter.description }}</p>
            <small>{{ chapter.estimated_days }} 天</small>
          </li>
        </ol>
      </div>

      <p v-if="errorMessage" style="color: #dc2626;">{{ errorMessage }}</p>
      <button class="primary-button" type="submit" :disabled="submitting">
        {{ submitting ? '创建中...' : '创建空间' }}
      </button>
    </form>
  </section>
</template>
