<script setup>
import { onMounted, ref } from "vue";
import UploadDropzone from "@/components/ingestion/UploadDropzone.vue";
import DocumentTable from "@/components/ingestion/DocumentTable.vue";
import { ingestionApi } from "@/api/ingestion";

const documents = ref([]);
const quality = ref(null);
const loading = ref(true);
const uploadError = ref("");

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
});

async function onUpload(files) {
  uploadError.value = "";
  try {
    await ingestionApi.uploadDocuments(files);
    await refresh();
  } catch (err) {
    uploadError.value = err.message;
  }
}

async function onRetry(doc) {
  await ingestionApi.retryDocument(doc.id);
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
      </section>

      <UploadDropzone @upload="onUpload" />
      <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>

      <p v-if="loading" class="loading-note">Loading…</p>
      <DocumentTable v-else :documents="documents" @retry="onRetry" />
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

.upload-error {
  color: var(--status-failed);
  font-size: 13px;
}

.loading-note {
  color: var(--text-faint);
  font-size: 13px;
}
</style>
