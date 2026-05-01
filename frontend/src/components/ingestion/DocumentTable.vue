<script setup>
import { useRouter } from "vue-router";
import SimilarityRule from "@/components/shared/SimilarityRule.vue";

const props = defineProps({ documents: { type: Array, required: true } });
const emit = defineEmits(["retry"]);
const router = useRouter();

const statusTone = { done: "done", failed: "failed", processing: "accent", pending: "pending" };

function openDetail(doc) {
  router.push({ name: "document-detail", params: { documentId: doc.id } });
}

function progress(doc) {
  return doc.total_pages ? doc.pages_done / doc.total_pages : 0;
}
</script>

<template>
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
      <tr v-for="doc in documents" :key="doc.id" class="doc-row" @click="openDetail(doc)">
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
        <td>
          <button v-if="doc.status === 'failed'" class="retry-btn" type="button" @click.stop="emit('retry', doc)">
            Retry
          </button>
        </td>
      </tr>
      <tr v-if="!documents.length">
        <td colspan="5" class="empty-cell">No documents yet — upload a PDF to get started.</td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
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

.empty-cell {
  text-align: center;
  color: var(--text-faint);
  padding: var(--space-6) !important;
}
</style>
