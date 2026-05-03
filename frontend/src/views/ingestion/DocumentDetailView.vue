<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import MetadataEditForm from "@/components/ingestion/MetadataEditForm.vue";
import { ingestionApi } from "@/api/ingestion";

const props = defineProps({ documentId: { type: String, required: true } });
const router = useRouter();

const doc = ref(null);
const loading = ref(true);
const saveNote = ref("");

async function load() {
  loading.value = true;
  doc.value = await ingestionApi.getDocument(props.documentId);
  loading.value = false;
}

onMounted(load);

async function retry() {
  await ingestionApi.retryDocument(props.documentId);
  await load();
}

async function saveMetadata(fields) {
  doc.value = await ingestionApi.updateMetadata(props.documentId, fields);
  saveNote.value = "Saved.";
  setTimeout(() => (saveNote.value = ""), 2000);
}
</script>

<template>
  <div class="detail">
    <button class="back-link" type="button" @click="router.push({ name: 'ingestion' })">← All documents</button>

    <p v-if="loading" class="loading-note">Loading…</p>

    <template v-else-if="doc">
      <header class="detail-header">
        <h1 class="detail-title">{{ doc.title || doc.file_name }}</h1>
        <div class="detail-meta">
          <span class="status-pill" :class="doc.status">{{ doc.status }}</span>
          <span class="mono">{{ doc.pages_done }}/{{ doc.total_pages }} pages</span>
          <button v-if="doc.status === 'failed'" class="retry-btn" type="button" @click="retry">
            Retry from checkpoint
          </button>
        </div>
        <p v-if="doc.last_error" class="last-error">{{ doc.last_error }}</p>
      </header>

      <section v-if="doc.running_summary" class="summary-block">
        <h2 class="section-label">Running summary</h2>
        <p class="summary-text">{{ doc.running_summary }}</p>
      </section>

      <section class="grid-2">
        <div>
          <h2 class="section-label">Metadata</h2>
          <MetadataEditForm :document="doc" @save="saveMetadata" />
          <p v-if="saveNote" class="save-note">{{ saveNote }}</p>
        </div>

        <div>
          <h2 class="section-label">Pages</h2>
          <ul class="page-list">
            <li v-for="page in doc.pages" :key="page.page_number" class="page-row">
              <span class="mono page-number">p.{{ page.page_number }}</span>
              <span class="status-pill sm" :class="page.processing_status">{{ page.processing_status }}</span>
              <span v-if="page.extractor_used" class="extractor mono">{{ page.extractor_used }}</span>
              <span v-if="page.is_short_page" class="tag">short page</span>
              <span v-if="page.has_summary" class="tag">summary</span>
              <span v-if="page.has_keywords" class="tag">keywords</span>
              <span v-if="page.error_message" class="page-error">{{ page.error_message }}</span>
            </li>
          </ul>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.detail {
  height: 100%;
  overflow-y: auto;
  max-width: 1000px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5) var(--space-8);
}

.back-link {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  padding: 0 0 var(--space-5);
}
.back-link:hover {
  color: var(--accent);
}

.detail-title {
  font-family: var(--font-serif);
  font-size: 24px;
  margin: 0 0 var(--space-2);
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-2);
}

.mono {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.last-error {
  color: var(--status-failed);
  font-size: 13px;
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
.status-pill.sm {
  padding: 1px 6px;
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

.section-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-faint);
  margin: 0 0 var(--space-3);
}

.summary-block {
  margin: var(--space-5) 0;
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--divider);
}

.summary-text {
  font-family: var(--font-serif);
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-muted);
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-7);
  margin-top: var(--space-5);
}

.save-note {
  color: var(--status-done);
  font-size: 12px;
  margin-top: var(--space-2);
}

.page-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 480px;
  overflow-y: auto;
}

.page-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border-bottom: 1px solid var(--divider);
  font-size: 12px;
  flex-wrap: wrap;
}

.page-number {
  width: 40px;
}

.extractor {
  color: var(--text-faint);
}

.tag {
  font-size: 10px;
  color: var(--text-muted);
  border: 1px solid var(--divider-strong);
  border-radius: 999px;
  padding: 1px 6px;
}

.page-error {
  color: var(--status-failed);
  font-size: 11px;
}

.loading-note {
  color: var(--text-faint);
  font-size: 13px;
}
</style>
