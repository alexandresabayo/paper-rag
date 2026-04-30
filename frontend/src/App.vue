<script setup>
import { RouterLink, RouterView, useRoute } from "vue-router";

const route = useRoute();
</script>

<template>
  <div class="shell">
    <header class="top-strip">
      <span class="wordmark">Paper RAG</span>
      <nav class="area-switch">
        <RouterLink to="/research" class="area-link" :class="{ active: route.path.startsWith('/research') }">
          Research
        </RouterLink>
        <RouterLink to="/ingestion" class="area-link" :class="{ active: route.path.startsWith('/ingestion') }">
          Ingestion
        </RouterLink>
      </nav>
    </header>
    <main class="area-body">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.top-strip {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--divider);
}

.wordmark {
  font-family: var(--font-serif);
  font-size: 15px;
  letter-spacing: 0.02em;
  color: var(--text-muted);
}

.area-switch {
  display: flex;
  gap: var(--space-5);
}

.area-link {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  text-decoration: none;
  padding-bottom: 2px;
  border-bottom: 1px solid transparent;
  transition: color 0.15s ease;
}

.area-link:hover {
  color: var(--text);
}

.area-link.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.area-body {
  flex: 1;
  min-height: 0;
}
</style>
