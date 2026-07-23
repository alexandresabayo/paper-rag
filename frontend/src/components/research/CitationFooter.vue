<script setup>
import { ref } from "vue";
import SimilarityRule from "@/components/shared/SimilarityRule.vue";
import PdfViewerModal from "./PdfViewerModal.vue";

defineProps({ sources: { type: Array, required: true } });

const activeSource = ref(null);

function openSource(source) {
  activeSource.value = source;
}

function closeViewer() {
  activeSource.value = null;
}
</script>

<template>
  <div v-if="sources.length" class="citations">
    <span class="citations-label">Sources</span>
    <div class="citation-list">
      <button
        v-for="(source, i) in sources"
        :key="i"
        type="button"
        class="citation"
        @click="openSource(source)"
      >
        <span class="citation-title">{{ source.document_title }}, p. {{ source.page_number }}</span>
        <SimilarityRule :value="source.similarity_score" :label="source.similarity_score.toFixed(2)" size="sm" />
      </button>
    </div>
  </div>

  <PdfViewerModal
    v-if="activeSource"
    :document-id="activeSource.document_id"
    :document-title="activeSource.document_title"
    :page-number="activeSource.page_number"
    @close="closeViewer"
  />
</template>

<style scoped>
.citations {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--divider);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.citations-label {
  font-size: 11px;
  color: var(--text-faint);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.citation-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.citation {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  text-decoration: none;
  background: none;
  border: none;
  padding: var(--space-1) 0;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
}

.citation-title {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.citation :deep(.rule-wrap) {
  flex: 0 0 auto;
  width: 100px;
}

.citation:hover .citation-title {
  color: var(--accent);
}
</style>
