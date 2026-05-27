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
        <span class="nav-link disabled" aria-disabled="true">Library</span>
        <span class="nav-link disabled" aria-disabled="true">Reviews</span>
        <span class="nav-link disabled" aria-disabled="true">Progress</span>
        <span class="nav-link disabled" aria-disabled="true">Settings</span>
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
