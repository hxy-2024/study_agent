# Frontend App Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the Fresh Teal Learning Workspace design to the existing Nuxt app shell and current pages.

**Architecture:** Keep this as a frontend-only polish PR. Use global CSS tokens and shared classes in `apps/web/assets/css/main.css`, keep page logic local to existing pages, and avoid introducing a component library or new runtime dependencies. The implementation should be done after the source-library upload UX branch is merged into the execution base, because the study-space detail page must preserve the source library interactions.

**Tech Stack:** Nuxt 4, Vue 3 `<script setup>`, TypeScript, Pinia, Vitest, Vue Test Utils, happy-dom, scoped Vue CSS, global CSS variables, `frontend-design` for final visual review.

---

## Scope Check

This plan implements:

`docs/superpowers/specs/2026-05-27-frontend-app-shell-design.md`

Execution base:

- Prefer `main` after `codex/source-library-upload-ux` is merged.
- If that PR is not merged yet, execute in `F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux` and preserve its existing source-library behavior.

In scope:

- Fresh teal global visual tokens.
- Light app shell with sidebar, top bar, model/runtime status, search affordance, and responsive layout.
- Dashboard reshaped around "Continue Learning" and supporting right rail panels.
- Create-space page reshaped into a clean workspace form.
- Study-space detail page visually aligned with the new shell while preserving source-library upload and RAG preview behavior if present in the execution base.
- Frontend tests for shell, dashboard, create-space behavior, and existing source-library behavior.
- Browser visual QA on desktop and mobile.

Out of scope:

- Route generation backend.
- Real global search.
- Real auth user menu.
- Dark mode.
- Installing a UI library.
- Extracting a full component package.
- Rewriting the chapter/chat experience.
- Complex animation libraries.

## File Structure

```text
apps/web/
  app.vue
  assets/
    css/
      main.css
  pages/
    index.vue
    spaces/
      new.vue
      [id]/
        index.vue
  tests/
    app-shell.spec.ts
    dashboard.spec.ts
    create-space.spec.ts
    source-library.spec.ts
```

Responsibilities:

- `apps/web/app.vue`: global app shell markup, sidebar navigation, top bar, main page slot.
- `apps/web/assets/css/main.css`: fresh teal tokens, layout primitives, buttons, forms, cards, badges, alerts, motion, reduced-motion rules, responsive rules.
- `apps/web/pages/index.vue`: dashboard structure centered on resume/continue learning.
- `apps/web/pages/spaces/new.vue`: create-space form visual structure, step indicator, action row.
- `apps/web/pages/spaces/[id]/index.vue`: align detail/source-library page with new shell and shared classes.
- `apps/web/tests/app-shell.spec.ts`: shell render tests.
- `apps/web/tests/dashboard.spec.ts`: dashboard render tests for empty and non-empty store states.
- `apps/web/tests/create-space.spec.ts`: keep existing behavior coverage and update selectors/text if needed.
- `apps/web/tests/source-library.spec.ts`: keep existing source-library coverage when the execution base includes it.

---

### Task 1: Prepare Worktree and Baseline

**Files:**
- Read: `apps/web/app.vue`
- Read: `apps/web/assets/css/main.css`
- Read: `apps/web/pages/index.vue`
- Read: `apps/web/pages/spaces/new.vue`
- Read: `apps/web/pages/spaces/[id]/index.vue`
- Read: `apps/web/tests/*.spec.ts`

- [ ] **Step 1: Enter the frontend execution worktree**

If `codex/source-library-upload-ux` has been merged into `main`, create a fresh worktree from `main`:

```powershell
cd F:\AIproject\study_agent
git worktree add .worktrees/codex-frontend-app-shell -b codex/frontend-app-shell
cd F:\AIproject\study_agent\.worktrees\codex-frontend-app-shell
```

If `codex/source-library-upload-ux` is not merged, continue inside:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-source-library-upload-ux
git branch --show-current
```

Expected:

- Fresh worktree branch is `codex/frontend-app-shell`, or existing branch is `codex/source-library-upload-ux`.
- The execution base contains the source-library upload UX if modifying `apps/web/pages/spaces/[id]/index.vue` source-library sections.

- [ ] **Step 2: Inspect current status**

Run:

```powershell
git status --short
git log --oneline -8
```

Expected:

- No unrelated tracked changes are staged.
- If `apps/web/package-lock.json` shows modified with empty `git diff`, do not stage it.

- [ ] **Step 3: Run baseline frontend tests**

Run:

```powershell
cd apps\web
npm run test
```

Expected:

- Existing Vitest tests pass before edits.
- If they fail because source-library polish is not merged into this base, stop and switch to the source-library worktree or merge that PR first.

Do not commit in this task.

---

### Task 2: Add App Shell Render Test

**Files:**
- Create: `apps/web/tests/app-shell.spec.ts`
- Modify later: `apps/web/app.vue`

- [ ] **Step 1: Write the failing shell test**

Create `apps/web/tests/app-shell.spec.ts`:

```ts
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
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
npm run test -- tests/app-shell.spec.ts
```

Expected:

- FAIL because the current shell still has the old dark sidebar and mojibake navigation text, and it does not render search/status/settings.

- [ ] **Step 3: Implement app shell markup**

Replace `apps/web/app.vue` with:

```vue
<template>
  <div class="app-shell">
    <aside class="sidebar" aria-label="Primary navigation">
      <NuxtLink class="brand-mark" to="/">
        <span class="brand-icon">S</span>
        <span>
          <strong>study_agent</strong>
          <small>Learning workspace</small>
        </span>
      </NuxtLink>

      <nav class="sidebar-nav">
        <NuxtLink class="nav-link" to="/">Spaces</NuxtLink>
        <NuxtLink class="nav-link" to="/">Library</NuxtLink>
        <NuxtLink class="nav-link" to="/">Reviews</NuxtLink>
        <NuxtLink class="nav-link" to="/">Progress</NuxtLink>
        <NuxtLink class="nav-link" to="/">Settings</NuxtLink>
      </nav>
    </aside>

    <div class="workspace-frame">
      <header class="topbar app-topbar">
        <label class="search-box">
          <span class="sr-only">Search</span>
          <input class="input search-input" type="search" placeholder="Search learning materials">
        </label>
        <div class="topbar-actions">
          <span class="runtime-pill">Model Ready</span>
          <button class="ghost-button" type="button">User</button>
        </div>
      </header>

      <main class="main">
        <NuxtPage />
      </main>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Add shell styles**

In `apps/web/assets/css/main.css`, replace the existing `.app-shell`, `.sidebar`, `.main`, `.topbar`, `.primary-button`, and `.card` rules later in Task 3. For this task, add the minimum shell-specific classes below existing rules so the test can pass:

```css
.workspace-frame {
  min-width: 0;
}

.brand-mark,
.sidebar-nav {
  display: grid;
}

.brand-mark {
  gap: 10px;
}

.sidebar-nav {
  gap: 8px;
  margin-top: 28px;
}

.app-topbar {
  gap: 16px;
}

.search-box {
  flex: 1;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
```

- [ ] **Step 5: Run shell test**

Run:

```powershell
npm run test -- tests/app-shell.spec.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add apps/web/app.vue apps/web/assets/css/main.css apps/web/tests/app-shell.spec.ts
git commit -m "feat: add frontend app shell structure"
```

---

### Task 3: Add Fresh Teal Design Tokens and Shared CSS

**Files:**
- Modify: `apps/web/assets/css/main.css`
- Test: `apps/web/tests/app-shell.spec.ts`

- [ ] **Step 1: Add CSS token assertion to shell test**

Append this test inside `describe('App shell', () => { ... })` in `apps/web/tests/app-shell.spec.ts`:

```ts
  it('loads the shared shell class names used by the design system', () => {
    const wrapper = mountShell()

    expect(wrapper.find('.app-shell').exists()).toBe(true)
    expect(wrapper.find('.sidebar').exists()).toBe(true)
    expect(wrapper.find('.primary-button').exists()).toBe(false)
    expect(wrapper.find('.runtime-pill').text()).toBe('Model Ready')
  })
```

This test protects class names used by later page work. CSS itself will be visually checked in Task 7.

- [ ] **Step 2: Run test**

Run:

```powershell
npm run test -- tests/app-shell.spec.ts
```

Expected: PASS or fail only if class names differ from Task 2.

- [ ] **Step 3: Replace global CSS with teal system**

Replace `apps/web/assets/css/main.css` with:

```css
:root {
  --color-page: #f3fbf9;
  --color-page-strong: #e6f7f3;
  --color-surface: #ffffff;
  --color-surface-muted: #ecfdf5;
  --color-border: #cce7e1;
  --color-border-strong: #8fd8ca;
  --color-text: #10201f;
  --color-muted: #58706b;
  --color-primary: #0f766e;
  --color-primary-bright: #14b8a6;
  --color-primary-soft: #ccfbf1;
  --color-success: #16a34a;
  --color-warning: #d97706;
  --color-error: #dc2626;
  --color-info: #2563eb;
  --shadow-card: 0 14px 40px rgba(15, 118, 110, 0.08);
  --shadow-hover: 0 18px 46px rgba(15, 118, 110, 0.14);
  color: var(--color-text);
  background: var(--color-page);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  background:
    linear-gradient(135deg, rgba(204, 251, 241, 0.65), rgba(255, 255, 255, 0) 38%),
    var(--color-page);
}

button,
input,
textarea,
select {
  font: inherit;
}

button,
a,
input,
textarea,
select {
  outline-color: var(--color-primary-bright);
}

a {
  color: inherit;
  text-decoration: none;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
}

.sidebar {
  min-height: 100vh;
  border-right: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(18px);
  padding: 22px 16px;
}

.workspace-frame {
  min-width: 0;
}

.brand-mark {
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 8px;
  padding: 8px;
}

.brand-icon {
  display: inline-grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: 8px;
  background: var(--color-primary);
  color: #fff;
  font-weight: 800;
}

.brand-mark strong,
.brand-mark small {
  display: block;
}

.brand-mark small {
  color: var(--color-muted);
  font-size: 12px;
  margin-top: 2px;
}

.sidebar-nav {
  display: grid;
  gap: 8px;
  margin-top: 28px;
}

.nav-link {
  position: relative;
  border-radius: 8px;
  color: var(--color-muted);
  font-weight: 700;
  padding: 10px 12px 10px 16px;
  transition: background-color 160ms ease, color 160ms ease, transform 160ms ease;
}

.nav-link:hover,
.nav-link.router-link-active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.nav-link.router-link-active::before {
  position: absolute;
  left: 6px;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 999px;
  background: var(--color-primary-bright);
  content: "";
}

.main {
  width: min(100%, 1320px);
  margin: 0 auto;
  padding: 24px;
}

.topbar {
  min-height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.app-topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  gap: 16px;
  border-bottom: 1px solid rgba(204, 231, 225, 0.8);
  background: rgba(243, 251, 249, 0.86);
  backdrop-filter: blur(18px);
  margin-bottom: 0;
  padding: 12px 24px;
}

.search-box {
  flex: 1;
  max-width: 620px;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.input,
.textarea,
.select {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-text);
  padding: 10px 12px;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.textarea {
  resize: vertical;
}

.input:focus,
.textarea:focus,
.select:focus {
  border-color: var(--color-primary-bright);
  box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.16);
}

.search-input {
  min-height: 40px;
}

.primary-button,
.secondary-button,
.ghost-button {
  min-height: 40px;
  border-radius: 8px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 800;
  padding: 10px 14px;
  transition: background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
  white-space: nowrap;
}

.primary-button {
  border: 1px solid var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.primary-button:hover {
  background: #0d9488;
  border-color: #0d9488;
  box-shadow: 0 10px 24px rgba(20, 184, 166, 0.28);
  transform: translateY(-1px);
}

.secondary-button {
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-primary);
}

.secondary-button:hover {
  border-color: var(--color-primary-bright);
  box-shadow: 0 8px 20px rgba(15, 118, 110, 0.12);
}

.ghost-button {
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-muted);
}

.ghost-button:hover {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.primary-button:disabled,
.secondary-button:disabled,
.ghost-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
}

.card,
.panel,
.metric-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: var(--shadow-card);
}

.card,
.panel {
  padding: 18px;
}

.card {
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.card:hover {
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-hover);
  transform: translateY(-1px);
}

.metric-card {
  padding: 14px;
}

.status-badge,
.runtime-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
  min-height: 28px;
  padding: 5px 9px;
}

.empty-state {
  border: 1px dashed var(--color-border-strong);
  border-radius: 8px;
  background: rgba(236, 253, 245, 0.72);
  color: var(--color-muted);
  padding: 18px;
}

.error-alert,
.success-alert {
  border-radius: 8px;
  margin-bottom: 16px;
  padding: 12px 14px;
}

.error-alert {
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: var(--color-error);
}

.success-alert {
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
  color: var(--color-success);
}

.form-field {
  display: grid;
  gap: 6px;
  color: var(--color-text);
  font-weight: 800;
}

.form-field span {
  color: var(--color-muted);
  font-size: 13px;
  font-weight: 600;
}

.page-enter {
  animation: page-enter 260ms ease both;
}

.skeleton {
  min-height: 80px;
  overflow: hidden;
  position: relative;
}

.skeleton::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(20, 184, 166, 0.12), transparent);
  content: "";
  transform: translateX(-100%);
  animation: shimmer 1.4s infinite;
}

@keyframes page-enter {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes shimmer {
  to {
    transform: translateX(100%);
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}

@media (max-width: 900px) {
  .app-shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    min-height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .sidebar-nav {
    grid-template-columns: repeat(5, minmax(0, 1fr));
    overflow-x: auto;
  }

  .nav-link {
    text-align: center;
    white-space: nowrap;
  }

  .app-topbar {
    align-items: stretch;
    flex-direction: column;
  }

  .topbar-actions {
    justify-content: space-between;
  }

  .main {
    padding: 16px;
  }
}

@media (max-width: 640px) {
  .topbar {
    align-items: stretch;
    flex-direction: column;
    height: auto;
  }

  .sidebar-nav {
    grid-template-columns: repeat(3, minmax(120px, 1fr));
  }

  .primary-button,
  .secondary-button,
  .ghost-button {
    width: 100%;
    white-space: normal;
  }
}
```

- [ ] **Step 4: Run shell test**

Run:

```powershell
npm run test -- tests/app-shell.spec.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/web/assets/css/main.css apps/web/tests/app-shell.spec.ts
git commit -m "feat: add fresh teal design system"
```

---

### Task 4: Redesign Dashboard Around Continue Learning

**Files:**
- Modify: `apps/web/pages/index.vue`
- Create: `apps/web/tests/dashboard.spec.ts`

- [ ] **Step 1: Write dashboard tests**

Create `apps/web/tests/dashboard.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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

describe('Dashboard page', () => {
  beforeEach(() => {
    storeState.loading = false
    storeState.spaces = []
    storeState.loadSpaces.mockReset()
  })

  it('renders the continue learning dashboard empty state', async () => {
    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(storeState.loadSpaces).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('Continue Learning')
    expect(wrapper.text()).toContain('Create your first study space')
    expect(wrapper.text()).toContain('New Study Space')
    expect(wrapper.text()).toContain('Today')
    expect(wrapper.text()).toContain('AI Mentor')
  })

  it('uses the first study space as the continue panel and keeps recent spaces below', async () => {
    storeState.spaces = [
      {
        id: '00000000-0000-0000-0000-000000000101',
        name: 'Python Backend Architecture',
        goal: 'Build production FastAPI services',
        status: 'active',
        target_days: 30
      },
      {
        id: '00000000-0000-0000-0000-000000000102',
        name: 'RAG Fundamentals',
        goal: 'Learn retrieval and citations',
        status: 'draft',
        target_days: 14
      }
    ]

    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Python Backend Architecture')
    expect(wrapper.text()).toContain('Build production FastAPI services')
    expect(wrapper.text()).toContain('Continue')
    expect(wrapper.text()).toContain('Recent Spaces')
    expect(wrapper.text()).toContain('RAG Fundamentals')
  })
})
```

- [ ] **Step 2: Run dashboard tests to verify failure**

Run:

```powershell
npm run test -- tests/dashboard.spec.ts
```

Expected:

- FAIL because the current dashboard still uses old text and a simple centered grid.

- [ ] **Step 3: Replace dashboard page**

Replace `apps/web/pages/index.vue` with:

```vue
<script setup lang="ts">
const store = useStudySpacesStore()

const primarySpace = computed(() => store.spaces[0] ?? null)
const recentSpaces = computed(() => store.spaces.slice(1))

onMounted(() => {
  store.loadSpaces()
})
</script>

<template>
  <section class="dashboard page-enter">
    <div class="dashboard-layout">
      <div class="dashboard-main">
        <div class="topbar page-heading">
          <div>
            <p class="eyebrow">Workspace</p>
            <h1>Continue Learning</h1>
            <p>Resume your current plan, review due knowledge, and keep source-backed study moving.</p>
          </div>
          <NuxtLink class="primary-button" to="/spaces/new">New Study Space</NuxtLink>
        </div>

        <div v-if="store.loading" class="card skeleton">Loading study spaces...</div>

        <section v-else-if="primarySpace" class="card continue-card">
          <div>
            <p class="eyebrow">Current space</p>
            <h2>{{ primarySpace.name }}</h2>
            <p>{{ primarySpace.goal }}</p>
          </div>
          <div class="progress-block" aria-label="Study progress">
            <span>Progress</span>
            <div class="progress-track">
              <div class="progress-fill" style="width: 42%;" />
            </div>
          </div>
          <div class="continue-actions">
            <span class="status-badge">{{ primarySpace.status }}</span>
            <NuxtLink class="primary-button" :to="`/spaces/${primarySpace.id}`">Continue</NuxtLink>
          </div>
        </section>

        <section v-else class="empty-state dashboard-empty">
          <div>
            <p class="eyebrow">Start here</p>
            <h2>Create your first study space</h2>
            <p>Set a learning goal, add source material, and let the agent prepare a focused route.</p>
          </div>
          <NuxtLink class="primary-button" to="/spaces/new">New Study Space</NuxtLink>
        </section>

        <section class="recent-section">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Library</p>
              <h2>Recent Spaces</h2>
            </div>
          </div>

          <div v-if="recentSpaces.length" class="space-grid">
            <NuxtLink v-for="space in recentSpaces" :key="space.id" class="card space-card" :to="`/spaces/${space.id}`">
              <span class="status-badge">{{ space.status }}</span>
              <h3>{{ space.name }}</h3>
              <p>{{ space.goal }}</p>
              <small>{{ space.target_days }} target days</small>
            </NuxtLink>
          </div>
          <p v-else class="empty-state">Recent spaces will appear here after you create more plans.</p>
        </section>
      </div>

      <aside class="dashboard-rail">
        <section class="metric-card">
          <p class="eyebrow">Today</p>
          <h2>Reviews</h2>
          <strong>0 due</strong>
          <p>No scheduled reviews yet.</p>
        </section>

        <section class="panel mentor-panel">
          <p class="eyebrow">AI Mentor</p>
          <h2>Next step</h2>
          <p>Create or continue a study space, then upload source material for grounded guidance.</p>
        </section>

        <section class="metric-card">
          <p class="eyebrow">Weekly progress</p>
          <h2>Focus</h2>
          <div class="progress-track">
            <div class="progress-fill" style="width: 18%;" />
          </div>
        </section>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.dashboard-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  gap: 18px;
  align-items: start;
}

.dashboard-main,
.dashboard-rail,
.recent-section {
  display: grid;
  gap: 18px;
}

.page-heading {
  min-height: 0;
  margin-bottom: 0;
}

.page-heading h1,
.continue-card h2,
.recent-section h2,
.dashboard-rail h2 {
  margin-bottom: 6px;
}

.page-heading p,
.continue-card p,
.space-card p,
.dashboard-rail p {
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

.continue-card {
  display: grid;
  gap: 16px;
}

.progress-block {
  display: grid;
  gap: 8px;
  color: var(--color-muted);
  font-weight: 700;
}

.progress-track {
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-primary-soft);
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-bright));
  animation: progress-in 420ms ease both;
}

.continue-actions,
.section-heading,
.dashboard-empty {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.space-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}

.space-card {
  display: grid;
  gap: 10px;
}

.space-card .status-badge {
  justify-self: start;
}

.metric-card strong {
  display: block;
  color: var(--color-primary);
  font-size: 28px;
  margin: 8px 0;
}

.mentor-panel {
  border-color: var(--color-border-strong);
}

@keyframes progress-in {
  from {
    transform: scaleX(0);
    transform-origin: left;
  }
  to {
    transform: scaleX(1);
    transform-origin: left;
  }
}

@media (max-width: 1000px) {
  .dashboard-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .continue-actions,
  .section-heading,
  .dashboard-empty {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
```

- [ ] **Step 4: Run dashboard tests**

Run:

```powershell
npm run test -- tests/dashboard.spec.ts
```

Expected: PASS.

- [ ] **Step 5: Run app shell and dashboard tests together**

Run:

```powershell
npm run test -- tests/app-shell.spec.ts tests/dashboard.spec.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add apps/web/pages/index.vue apps/web/tests/dashboard.spec.ts
git commit -m "feat: redesign dashboard workspace"
```

---

### Task 5: Redesign Create Study Space Page

**Files:**
- Modify: `apps/web/pages/spaces/new.vue`
- Modify: `apps/web/tests/create-space.spec.ts`

- [ ] **Step 1: Update create-space test for design structure**

Modify `apps/web/tests/create-space.spec.ts` so it asserts the existing AI render button and submit button still exist, plus the new step/workspace labels. The full test should be:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://localhost:8000/api/v1'
  }
}))
vi.stubGlobal('useRouter', () => ({
  push: vi.fn()
}))

const { default: NewSpacePage } = await import('../pages/spaces/new.vue')

describe('NewSpacePage', () => {
  it('renders the redesigned workspace form and create controls', () => {
    const wrapper = mount(NewSpacePage)

    expect(wrapper.text()).toContain('Create Study Space')
    expect(wrapper.text()).toContain('Goal')
    expect(wrapper.text()).toContain('Source setup')
    expect(wrapper.text()).toContain('Route preview')
    expect(wrapper.text()).toContain('AI Render')
    expect(wrapper.text()).toContain('Create Space')
  })
})
```

- [ ] **Step 2: Run create-space test to verify failure**

Run:

```powershell
npm run test -- tests/create-space.spec.ts
```

Expected:

- FAIL because the current page still uses old/mojibake text and inline styles.

- [ ] **Step 3: Replace create-space page**

Replace `apps/web/pages/spaces/new.vue` with:

```vue
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
```

- [ ] **Step 4: Run create-space test**

Run:

```powershell
npm run test -- tests/create-space.spec.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/web/pages/spaces/new.vue apps/web/tests/create-space.spec.ts
git commit -m "feat: redesign create space workspace"
```

---

### Task 6: Align Study Space Detail and Source Library

**Files:**
- Modify: `apps/web/pages/spaces/[id]/index.vue`
- Test: `apps/web/tests/source-library.spec.ts` if present

- [ ] **Step 1: Check source-library base**

Run:

```powershell
Test-Path apps\web\tests\source-library.spec.ts
Select-String -LiteralPath apps\web\pages\spaces\[id]\index.vue -Pattern "Source library|Upload learning material|Run ingestion|Chunk preview"
```

Expected:

- If `source-library.spec.ts` exists and the page contains source-library UI, preserve all existing behavior and continue with Steps 2-5.
- If it does not exist, only apply the page header and simple route shell styling in Step 6.

- [ ] **Step 2: Add or keep source-library regression tests**

If `apps/web/tests/source-library.spec.ts` exists, run:

```powershell
npm run test -- tests/source-library.spec.ts
```

Expected: PASS before styling edits.

If this fails, fix the base before applying visual changes.

- [ ] **Step 3: Apply design alignment to source-library page**

In `apps/web/pages/spaces/[id]/index.vue`, keep existing script logic and API helpers. Only adjust template copy/classes and scoped CSS.

Use these structural requirements:

```vue
<section class="space-detail page-enter">
  <div class="space-layout">
    <div class="space-main">
      <div class="topbar page-heading">
        <div>
          <p class="eyebrow">Study space</p>
          <h1>Study Space</h1>
          <p>Space ID: {{ spaceId }}</p>
        </div>
      </div>

      <section class="card route-overview">
        <div>
          <p class="eyebrow">Next action</p>
          <h2>Learning route foundation</h2>
          <p>Route generation will connect chapters, source chunks, and tutor sessions in the next product phase.</p>
        </div>
      </section>

      <!-- Existing source upload and source list sections remain below. -->
    </div>

    <aside class="space-rail">
      <section class="panel">
        <p class="eyebrow">AI Mentor</p>
        <h2>Ready for sources</h2>
        <p>Upload text or Markdown material, run ingestion, then inspect chunks before route generation.</p>
      </section>

      <!-- Existing chunk preview can live here if the current page already uses an aside. -->
    </aside>
  </div>
</section>
```

Do not remove:

- File picker.
- Upload button.
- Source filters and counts.
- `Retry ingestion` and `Re-run ingestion`.
- `data-testid="preview-run-ingestion"`.
- Protected auth headers in `$fetch` calls.

- [ ] **Step 4: Replace hardcoded colors in source-library scoped CSS**

In `apps/web/pages/spaces/[id]/index.vue`, update scoped CSS colors to use global variables where practical:

```css
.eyebrow {
  color: var(--color-primary);
}

.muted,
.empty-state,
.source-meta,
.selected-file {
  color: var(--color-muted);
}

.file-picker {
  border-color: var(--color-border-strong);
  background: var(--color-surface-muted);
}

.selected-file-panel,
.source-row,
.chunk-card {
  border-color: var(--color-border);
}

.filter-button.active,
.source-row.active {
  border-color: var(--color-primary-bright);
  color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.14);
}

.upload-phase {
  color: var(--color-primary);
}
```

Keep the rest of the responsive behavior intact.

- [ ] **Step 5: Run source-library tests**

Run:

```powershell
npm run test -- tests/source-library.spec.ts
```

Expected: PASS.

- [ ] **Step 6: If source-library UX is not in base, apply minimal detail page design**

If the execution base only has the simple detail page, replace `apps/web/pages/spaces/[id]/index.vue` with:

```vue
<script setup lang="ts">
const route = useRoute()
</script>

<template>
  <section class="space-detail page-enter">
    <div class="space-layout">
      <div class="space-main">
        <div class="topbar page-heading">
          <div>
            <p class="eyebrow">Study space</p>
            <h1>Study Space</h1>
            <p>Space ID: {{ route.params.id }}</p>
          </div>
        </div>

        <section class="card route-overview">
          <p class="eyebrow">Next action</p>
          <h2>Learning route foundation</h2>
          <p>Route generation will connect chapters, source chunks, RAG, and study sessions in the next product phase.</p>
        </section>
      </div>

      <aside class="space-rail">
        <section class="panel">
          <p class="eyebrow">AI Mentor</p>
          <h2>Prepare sources</h2>
          <p>Upload and ingestion controls will appear here after the source library branch is merged.</p>
        </section>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.space-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  gap: 18px;
  align-items: start;
}

.space-main,
.space-rail {
  display: grid;
  gap: 18px;
}

.page-heading {
  min-height: 0;
}

.page-heading p,
.route-overview p,
.space-rail p {
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

@media (max-width: 1000px) {
  .space-layout {
    grid-template-columns: 1fr;
  }
}
</style>
```

- [ ] **Step 7: Run relevant tests**

If source-library test exists:

```powershell
npm run test -- tests/source-library.spec.ts
```

If source-library test does not exist:

```powershell
npm run test
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add apps/web/pages/spaces/[id]/index.vue apps/web/tests/source-library.spec.ts
git commit -m "feat: align study space workspace styling"
```

If `source-library.spec.ts` does not exist or was not modified, omit it from `git add`.

---

### Task 7: Final Verification and Browser Visual QA

**Files:**
- Read: `apps/web/app.vue`
- Read: `apps/web/assets/css/main.css`
- Read: `apps/web/pages/index.vue`
- Read: `apps/web/pages/spaces/new.vue`
- Read: `apps/web/pages/spaces/[id]/index.vue`

- [ ] **Step 1: Run full frontend tests**

Run:

```powershell
cd F:\AIproject\study_agent\.worktrees\codex-frontend-app-shell\apps\web
npm run test
```

If executing in the source-library worktree, use that worktree path instead.

Expected:

- All Vitest tests pass.

- [ ] **Step 2: Run typecheck**

Run:

```powershell
npm run typecheck
```

Expected:

- Exit code 0.
- Existing Vue language plugin warning can be recorded if no TypeScript errors are emitted.

- [ ] **Step 3: Run production build**

Run:

```powershell
npm run build
```

Expected:

- Exit code 0.
- Existing Nuxt sourcemap or deprecation warnings can be recorded if build completes.

- [ ] **Step 4: Start dev server for visual QA**

Run:

```powershell
npm run dev -- --host 127.0.0.1 --port 3011
```

If the assistant cannot start a long-running server due sandbox limits, ask the user to run the same command manually.

- [ ] **Step 5: Browser visual QA**

Open:

```text
http://127.0.0.1:3011/
http://127.0.0.1:3011/spaces/new
http://127.0.0.1:3011/spaces/00000000-0000-0000-0000-000000000101
```

Check desktop width:

- Sidebar is light, teal-accented, and not dark.
- Topbar search and runtime status fit.
- Dashboard centers the continue-learning task, not decorative cards.
- Right rail supports Today/AI Mentor/Progress.
- Buttons use teal and have hover/focus states.
- Cards lift subtly and do not feel like nested cards.

Check mobile width:

- Sidebar/nav wraps or scrolls without overlap.
- Buttons do not overflow.
- Dashboard and create page stack into one column.
- Long IDs and source names wrap.
- Source-library actions remain usable.

- [ ] **Step 6: Fix visual regressions if found**

If visual QA finds text overlap or broken responsive layout, edit only the relevant CSS in:

```text
apps/web/assets/css/main.css
apps/web/pages/index.vue
apps/web/pages/spaces/new.vue
apps/web/pages/spaces/[id]/index.vue
```

Then rerun:

```powershell
npm run test
npm run typecheck
npm run build
```

- [ ] **Step 7: Commit visual fixes**

If fixes were needed:

```powershell
git add apps/web/assets/css/main.css apps/web/pages/index.vue apps/web/pages/spaces/new.vue apps/web/pages/spaces/[id]/index.vue
git commit -m "fix: polish frontend responsive layout"
```

If no fixes were needed, do not create an empty commit.

## Final Verification

Before push/PR, record:

```powershell
cd apps\web
npm run test
npm run typecheck
npm run build
```

Expected:

- Vitest passes.
- Typecheck exits 0.
- Build exits 0.

## Execution Order

1. Ensure the source-library upload UX branch is merged, or execute in that worktree.
2. Execute Tasks 1-7 in order.
3. Preserve the worktree for visual review and PR feedback.
4. Push branch and open or update PR.

## Self-Review

- Spec coverage: Tasks cover app shell, teal tokens, motion, dashboard, create page, study-space detail/source-library alignment, tests, and visual QA.
- Scope control: No backend, no UI library installation, no route generation, no real search/auth behavior.
- Type consistency: The plan uses existing Nuxt/Vue patterns, `useStudySpacesStore`, `NuxtLink`, `NuxtPage`, and Vitest setup.
- Frontend-design alignment: The visual direction is fresh teal, restrained, task-centered, responsive, and avoids marketing hero layout, decorative card centers, nested cards, and excessive animation.
