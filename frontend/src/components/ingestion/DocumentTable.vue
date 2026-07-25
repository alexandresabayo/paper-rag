<script setup>
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import SimilarityRule from "@/components/shared/SimilarityRule.vue";

const props = defineProps({ documents: { type: Array, required: true } });
const emit = defineEmits(["retry", "delete"]);
const router = useRouter();

const statusTone = { done: "done", failed: "failed", processing: "accent", pending: "pending" };

// ISSUE-024 (AGENT_TASKS.md): client-side sort/filter - a plain
// computed over `props.documents`, not a server round trip. Fine at
// this corpus's stated scale (README: "personal/small-team"); revisit
// server-side only if that scope ever changes.
const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "processing", label: "Processing" },
  { value: "done", label: "Done" },
  { value: "failed", label: "Failed" },
];

const SORT_OPTIONS = [
  { value: "uploaded_desc", label: "Newest first" },
  { value: "uploaded_asc", label: "Oldest first" },
  { value: "name_asc", label: "Name (A–Z)" },
  { value: "status", label: "Status" },
  { value: "metadata", label: "Metadata completeness" },
];

// Sort order within a column, most-attention-needed first - e.g.
// "Status" surfaces failed documents before pending/processing before
// the ones already done and needing nothing further from the admin.
const STATUS_SORT_ORDER = { failed: 0, processing: 1, pending: 2, done: 3 };
const METADATA_SORT_ORDER = { na: 0, pending: 1, done: 2 };

const statusFilter = ref("all");
const sortBy = ref("uploaded_desc");

function statusCount(value) {
  if (value === "all") return props.documents.length;
  return props.documents.filter((d) => d.status === value).length;
}

const visibleDocuments = computed(() => {
  let rows = props.documents;
  if (statusFilter.value !== "all") {
    rows = rows.filter((d) => d.status === statusFilter.value);
  }
  rows = [...rows];

  switch (sortBy.value) {
    case "uploaded_asc":
      rows.sort((a, b) => a.created_at.localeCompare(b.created_at));
      break;
    case "name_asc":
      rows.sort((a, b) => (a.title || a.file_name).localeCompare(b.title || b.file_name));
      break;
    case "status":
      rows.sort((a, b) => (STATUS_SORT_ORDER[a.status] ?? 9) - (STATUS_SORT_ORDER[b.status] ?? 9));
      break;
    case "metadata":
      rows.sort((a, b) => (METADATA_SORT_ORDER[a.metadata_status] ?? 9) - (METADATA_SORT_ORDER[b.metadata_status] ?? 9));
      break;
    case "uploaded_desc":
    default:
      rows.sort((a, b) => b.created_at.localeCompare(a.created_at));
      break;
  }
  return rows;
});

function openDetail(doc) {
  router.push({ name: "document-detail", params: { documentId: doc.id } });
}

function progress(doc) {
  return doc.total_pages ? doc.pages_done / doc.total_pages : 0;
}
</script>

<template>
  <div class="table-wrap">
    <div class="table-toolbar">
      <div class="status-filter" role="radiogroup" aria-label="Filter by status">
        <button
          v-for="f in STATUS_FILTERS"
          :key="f.value"
          type="button"
          class="filter-chip"
          role="radio"
          :aria-checked="statusFilter === f.value"
          :class="{ active: statusFilter === f.value }"
          @click="statusFilter = f.value"
        >
          {{ f.label }} <span class="filter-count">{{ statusCount(f.value) }}</span>
        </button>
      </div>

      <label class="sort-control">
        Sort
        <select v-model="sortBy" aria-label="Sort documents by">
          <option v-for="opt in SORT_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </label>
    </div>

    <table class="doc-table">
      <thead>
        <tr>
          <th>Document</th>
          <th>Pages</th>
          <th>Status</th>
          <th>Metadata</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="doc in visibleDocuments" :key="doc.id" class="doc-row" @click="openDetail(doc)">
          <td>
            <div class="doc-name">{{ doc.title || doc.file_name }}</div>
            <div class="doc-sub">{{ doc.file_name }}</div>
          </td>
          <td class="mono-cell">
            <SimilarityRule
              :value="progress(doc)"
              :label="`${doc.pages_done}/${doc.total_pages}`"
              :tone="statusTone[doc.status] || 'pending'"
              size="md"
            />
          </td>
          <td>
            <span class="status-pill" :class="doc.status">{{ doc.status }}</span>
            <span v-if="doc.pages_failed" class="warn-note mono-cell">{{ doc.pages_failed }} failed</span>
            <span v-if="doc.pages_used_fallback" class="warn-note mono-cell">{{ doc.pages_used_fallback }} fallback</span>
          </td>
          <td class="mono-cell">{{ doc.metadata_status }}</td>
          <td class="actions-cell">
            <button v-if="doc.status === 'failed'" class="retry-btn" type="button" @click.stop="emit('retry', doc)">
              Retry
            </button>
            <button class="delete-btn" type="button" title="Delete document" @click.stop="emit('delete', doc)">
              Delete
            </button>
          </td>
        </tr>
        <tr v-if="!visibleDocuments.length">
          <td colspan="5" class="empty-cell">
            {{ documents.length ? "No documents match this filter." : "No documents yet — upload a PDF to get started." }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.status-filter {
  display: inline-flex;
  border: 1px solid var(--divider-strong);
  border-radius: var(--radius-md);
  padding: 2px;
  gap: 2px;
}

.filter-chip {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 500;
  padding: 5px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.filter-chip:hover {
  color: var(--text);
}

.filter-chip.active {
  background: var(--accent-dim);
  color: var(--accent);
}

.filter-count {
  font-family: var(--font-mono);
  color: var(--text-faint);
}

.filter-chip.active .filter-count {
  color: var(--accent);
}

.sort-control {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--text-faint);
}

.sort-control select {
  background: var(--bg-sunken);
  border: 1px solid var(--divider-strong);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: 12px;
  padding: 4px 8px;
}

.sort-control select:focus {
  outline: none;
  border-color: var(--accent);
}

.doc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

thead th {
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-faint);
  font-weight: 500;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--divider);
}

.doc-row {
  cursor: pointer;
  transition: background 0.1s ease;
}

.doc-row:hover {
  background: var(--bg-hover);
}

.doc-row td {
  padding: var(--space-3);
  border-bottom: 1px solid var(--divider);
  vertical-align: middle;
}

.doc-name {
  color: var(--text);
}

.doc-sub {
  color: var(--text-faint);
  font-size: 11px;
  margin-top: 2px;
}

.mono-cell {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.status-pill {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--divider-strong);
  color: var(--text-muted);
}

.status-pill.done {
  color: var(--status-done);
  border-color: var(--status-done);
}
.status-pill.failed {
  color: var(--status-failed);
  border-color: var(--status-failed);
}
.status-pill.processing {
  color: var(--accent);
  border-color: var(--accent);
}

.warn-note {
  display: block;
  margin-top: 4px;
}

.actions-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}

.retry-btn {
  background: var(--accent-dim);
  color: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}

.retry-btn:hover {
  background: var(--accent-dim-strong);
}

.delete-btn {
  background: transparent;
  color: var(--text-faint);
  border: 1px solid var(--divider-strong);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease;
}

.delete-btn:hover {
  color: var(--status-failed);
  border-color: var(--status-failed);
}

.empty-cell {
  text-align: center;
  color: var(--text-faint);
  padding: var(--space-6) !important;
}
</style>
