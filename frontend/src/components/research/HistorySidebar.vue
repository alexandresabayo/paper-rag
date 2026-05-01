<script setup>
defineProps({
  items: { type: Array, required: true },
  collapsed: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
});
defineEmits(["select", "toggle-collapsed"]);

function preview(text) {
  return text.length > 64 ? `${text.slice(0, 64)}…` : text;
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <button class="collapse-toggle" type="button" @click="$emit('toggle-collapsed')">
      {{ collapsed ? "›" : "‹" }}
    </button>
    <template v-if="!collapsed">
      <h2 class="sidebar-title">History</h2>
      <p v-if="loading" class="empty">Loading…</p>
      <p v-else-if="!items.length" class="empty">No queries yet.</p>
      <ul v-else class="history-list">
        <li v-for="item in items" :key="item.id">
          <button class="history-item" type="button" @click="$emit('select', item)">
            {{ preview(item.query_text) }}
          </button>
        </li>
      </ul>
    </template>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px;
  flex: none;
  background: var(--bg-raised);
  border-right: 1px solid var(--divider);
  padding: var(--space-4);
  position: relative;
  overflow-y: auto;
  transition: width 0.2s ease;
}

.sidebar.collapsed {
  width: 32px;
  padding: var(--space-4) 0;
}

.collapse-toggle {
  position: absolute;
  top: var(--space-3);
  right: var(--space-2);
  background: none;
  border: none;
  color: var(--text-faint);
  cursor: pointer;
  font-size: 14px;
  padding: var(--space-1) var(--space-2);
}

.collapse-toggle:hover {
  color: var(--text);
}

.sidebar-title {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-faint);
  margin: 0 0 var(--space-4);
}

.empty {
  font-size: 12px;
  color: var(--text-faint);
}

.history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 13px;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  line-height: 1.4;
}

.history-item:hover {
  background: var(--bg-hover);
  color: var(--text);
}
</style>
