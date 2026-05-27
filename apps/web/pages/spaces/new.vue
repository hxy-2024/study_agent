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
      title: 'Clarify the learning goal',
      description: `Define the scope, existing foundation, and completion criteria for ${form.goal || 'this study goal'}.`,
      estimated_days: first
    },
    {
      order: 2,
      title: 'Build the core knowledge map',
      description: 'Break source material into key concepts and connect them into a usable learning structure.',
      estimated_days: second
    },
    {
      order: 3,
      title: 'Review, test, and reinforce',
      description: 'Use quizzes, weak-point review, and spaced practice to check mastery.',
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
    errorMessage.value = error instanceof Error ? error.message : 'Failed to create study space'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="create-space page-enter">
    <div class="topbar page-heading">
      <div>
        <p class="eyebrow">New workspace</p>
        <h1>Create Study Space</h1>
        <p>Set the learning goal, prepare sources, and preview a route before creating the space.</p>
      </div>
    </div>

    <div class="step-strip" aria-label="Creation steps">
      <span class="active">1 Goal</span>
      <span>2 Source setup</span>
      <span>3 Route preview</span>
    </div>

    <form class="create-layout" @submit.prevent="createSpace">
      <section class="card form-panel">
        <div>
          <p class="eyebrow">Goal</p>
          <h2>Learning setup</h2>
        </div>

        <label class="form-field">
          Space name
          <input v-model="form.name" class="input" required maxlength="160">
        </label>

        <label class="form-field">
          Learning goal
          <textarea v-model="form.goal" class="textarea" required rows="5" />
        </label>

        <div class="field-grid">
          <label class="form-field">
            Level
            <select v-model="form.level" class="select">
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </label>

          <label class="form-field">
            Intensity
            <select v-model="form.intensity" class="select">
              <option value="light">Light</option>
              <option value="normal">Normal</option>
              <option value="intensive">Intensive</option>
            </select>
          </label>

          <label class="form-field">
            Target days
            <input v-model.number="form.target_days" class="input" type="number" min="1" max="365">
          </label>
        </div>
      </section>

      <aside class="create-side">
        <section class="panel source-setup">
          <p class="eyebrow">Source setup</p>
          <h2>Materials</h2>
          <p>Upload and source parsing are handled in the study space library. This step stays reserved for the richer import flow.</p>
        </section>

        <section class="panel route-panel">
          <div class="route-heading">
            <div>
              <p class="eyebrow">Route preview</p>
              <h2>Draft route</h2>
            </div>
            <button class="secondary-button" type="button" @click="renderDraftRoute">AI Render</button>
          </div>

          <ol v-if="routeOutline.length" class="route-list">
            <li v-for="chapter in routeOutline" :key="chapter.order">
              <strong>{{ chapter.title }}</strong>
              <p>{{ chapter.description }}</p>
              <small>{{ chapter.estimated_days }} days</small>
            </li>
          </ol>
          <p v-else class="empty-state">Generate a route draft after filling in the learning goal.</p>
        </section>

        <p v-if="errorMessage" class="error-alert">{{ errorMessage }}</p>

        <div class="action-row">
          <NuxtLink class="ghost-button" to="/">Cancel</NuxtLink>
          <button class="primary-button" type="submit" :disabled="submitting">
            {{ submitting ? 'Creating...' : 'Create Space' }}
          </button>
        </div>
      </aside>
    </form>
  </section>
</template>

<style scoped>
.page-heading {
  min-height: 0;
}

.page-heading p,
.source-setup p,
.route-list p {
  color: var(--color-muted);
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.step-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
}

.step-strip span {
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-muted);
  font-weight: 800;
  padding: 7px 10px;
}

.step-strip .active {
  border-color: var(--color-primary-bright);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.create-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 18px;
  align-items: start;
}

.form-panel,
.create-side,
.route-panel {
  display: grid;
  gap: 16px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.route-heading,
.action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.route-list {
  display: grid;
  gap: 12px;
  margin: 0;
  padding-left: 22px;
}

.route-list li::marker {
  color: var(--color-primary);
  font-weight: 800;
}

.route-list small {
  color: var(--color-primary);
  font-weight: 800;
}

@media (max-width: 1000px) {
  .create-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .field-grid {
    grid-template-columns: 1fr;
  }

  .route-heading,
  .action-row {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
