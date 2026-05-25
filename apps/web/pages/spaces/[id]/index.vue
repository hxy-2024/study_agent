<script setup lang="ts">
const route = useRoute()
</script>

<template>
  <section>
    <div class="topbar">
      <div>
        <h1>学习空间</h1>
        <p>空间 ID：{{ route.params.id }}</p>
      </div>
    </div>
    <div class="card">
      <h2>学习路线</h2>
      <p>下一阶段计划会在这里接入章节、资料库、RAG 和会话学习页。</p>
    </div>
  </section>
</template>
