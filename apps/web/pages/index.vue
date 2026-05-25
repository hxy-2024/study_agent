<script setup lang="ts">
const store = useStudySpacesStore()

onMounted(() => {
  store.loadSpaces()
})
</script>

<template>
  <section>
    <div class="topbar">
      <div>
        <h1>学习空间</h1>
        <p>继续学习、查看待复习内容，或创建新的学习计划。</p>
      </div>
      <NuxtLink class="primary-button" to="/spaces/new">新建学习空间</NuxtLink>
    </div>

    <div v-if="store.loading" class="card">正在加载学习空间...</div>
    <div v-else-if="store.spaces.length === 0" class="card">
      <h2>还没有学习空间</h2>
      <p>创建一个学习空间，上传教材并生成学习路线。</p>
      <NuxtLink class="primary-button" to="/spaces/new">开始创建</NuxtLink>
    </div>
    <div
      v-else
      style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px;"
    >
      <NuxtLink v-for="space in store.spaces" :key="space.id" class="card" :to="`/spaces/${space.id}`">
        <h2>{{ space.name }}</h2>
        <p>{{ space.goal }}</p>
        <small>{{ space.status }} · {{ space.target_days }} 天</small>
      </NuxtLink>
    </div>
  </section>
</template>
