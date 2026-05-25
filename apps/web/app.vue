<template>
  <div class="app-shell">
    <aside class="sidebar">
      <strong>study_agent</strong>
      <nav style="display: grid; gap: 12px; margin-top: 24px;">
        <NuxtLink to="/">学习空间</NuxtLink>
        <NuxtLink to="/">待复习</NuxtLink>
        <NuxtLink to="/">资料库</NuxtLink>
        <NuxtLink to="/">学习画像</NuxtLink>
      </nav>
    </aside>
    <main class="main">
      <NuxtPage />
    </main>
  </div>
</template>
