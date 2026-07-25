<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import UploadDropzone from "@/components/ingestion/UploadDropzone.vue";
import DocumentTable from "@/components/ingestion/DocumentTable.vue";
import QualityDrilldown from "@/components/ingestion/QualityDrilldown.vue";
import { ingestionApi } from "@/api/ingestion";

const documents = ref([]);
const quality = ref(null);
const loading = ref(true);
const uploadError = ref("");
const retryAllPending = ref(false);

// ISSUE-020 (AGENT_TASKS.md): live progress updates. Polling (the
// simplest of the two options that issue names), not a push channel -
// this dashboard already refetches on every mount/action, so a timed
// refetch that stops itself once nothing is actively processing is a
// small, low-risk extension of the same pattern rather than new
// infrastructure (SSE/WebSockets) for a single-admin tool. Recursive
// `setTimeout` rather than `setInterval` so a slow request can't stack
// overlapping polls - the next poll is only scheduled once the
// previous refresh has actually finished.
const POLL_INTERVAL_MS = 3000;
let pollTimer = null;

function hasActiveDocuments() {
  return documents.value.some((d) => d.status === "pending" || d.status === "processing");
}

function clearPoll() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function schedulePoll() {
  clearPoll();
  if (!hasActiveDocuments()) return;
  pollTimer = setTimeout(async () => {
    await refresh();
    schedulePoll();
  }, POLL_INTERVAL_MS);
}

async function refresh() {
  const [docs, report] = await Promise.all([ingestionApi.listDocuments(), ingestionApi.getQualityReport()]);
  documents.value = docs;
  quality.value = report;
}

onMounted(async () => {
  loading.value = true;
  try {
    await refresh();
  } finally {
    loading.value = false;
  }
  schedulePoll();
});

onUnmounted(clearPoll);

async function onUpload(files) {
  uploadError.value = "";
  try {
    await ingestionApi.uploadDocuments(files);
    await refresh();
    schedulePoll(); // a fresh upload may now be the only active document
  } catch (err) {
    uploadError.value = err.message;
  }
}

async function onRetry(doc) {
  await ingestionApi.retryDocument(doc.id);
  await refresh();
  schedulePoll();
}

// ISSUE-022: bulk "retry all failed".
async function onRetryAllFailed() {
  retryAllPending.value = true;
  try {
    await ingestionApi.retryAllFailed();
    await refresh();
    schedulePoll();
  } finally {
    retryAllPending.value = false;
  }
}

// ISSUE-023: document deletion. A plain confirm() rather than a new
// modal component - this is the only destructive action in the whole
// dashboard, so a bespoke confirmation UI isn't earning its keep yet.
async function onDelete(doc) {
  const label = doc.title || doc.file_name;
  if (!window.confirm(`Delete "${label}"? This removes the document, its pages, and its vectors. This cannot be undone.`)) {
    return;
  }
  await ingestionApi.deleteDocument(doc.id);
  await refresh();
}
</script>

<template>
  <div class="ingestion">
    <div class="ingestion-body">
      <section class="quality-strip" v-if="quality">
        <div class="quality-stat">
          <span class="quality-value">{{ quality.documents.total_documents }}</span>
          <span class="quality-label">documents</span>
        </div>
        <div class="quality-stat">
          <span class="quality-value">{{ quality.documents.documents_done || 0 }}</span>
          <span class="quality-label">done</span>
        </div>
        <div class="quality-stat">
          <span class="quality-value" :class="{ warn: quality.documents.documents_failed }">{{
            quality.documents.documents_failed || 0
          }}</span>
          <span class="quality-label">failed</span>
        </div>
        <div class="quality-stat">
          <span class="quality-value" :class="{ warn: quality.documents.documents_with_na_metadata }">{{
            quality.documents.documents_with_na_metadata || 0
          }}</span>
          <span class="quality-label">metadata N/A</span>
        </div>
        <div class="quality-stat">
          <span class="quality-value" :class="{ warn: quality.pages.pages_used_fallback }">{{
            quality.pages.pages_used_fallback || 0
          }}</span>
          <span class="quality-label">pages via fallback</span>
        </div>

        <button
          v-if="quality.documents.documents_failed"
          class="retry-all-btn"
          type="button"
          :disabled="retryAllPending"
          @click="onRetryAllFailed"
        >
          {{ retryAllPending ? "Retrying…" : "Retry all failed" }}
        </button>
      </section>

      <QualityDrilldown v-if="quality" :quality="quality" />

      <UploadDropzone @upload="onUpload" />
      <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>

      <p v-if="loading" class="loading-note">Loading…</p>
      <DocumentTable v-else :documents="documents" @retry="onRetry" @delete="onDelete" />
    </div>
  </div>
</template>

<style scoped>
.ingestion {
  height: 100%;
  overflow-y: auto;
}

.ingestion-body {
  max-width: 1000px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.quality-strip {
  display: flex;
  align-items: center;
  gap: var(--space-7);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--divider);
}

.quality-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.quality-value {
  font-family: var(--font-mono);
  font-size: 22px;
  color: var(--text);
}

.quality-value.warn {
  color: var(--status-failed);
}

.quality-label {
  font-size: 11px;
  color: var(--text-faint);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.retry-all-btn {
  margin-left: auto;
  background: transparent;
  color: var(--status-failed);
  border: 1px solid var(--status-failed);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-3);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease;
  white-space: nowrap;
}

.retry-all-btn:hover:not(:disabled) {
  background: rgba(196, 102, 79, 0.14);
}

.retry-all-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.upload-error {
  color: var(--status-failed);
  font-size: 13px;
}

.loading-note {
  color: var(--text-faint);
  font-size: 13px;
}
</style>
