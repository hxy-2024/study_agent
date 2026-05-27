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
          <span class="sr-only">Search learning materials</span>
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
