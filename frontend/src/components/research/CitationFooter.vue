<script setup>
import SimilarityRule from "@/components/shared/SimilarityRule.vue";
import { researchApi } from "@/api/research";

defineProps({ sources: { type: Array, required: true } });
</script>

<template>
  <div v-if="sources.length" class="citations">
    <span class="citations-label">Sources</span>
    <a
      v-for="(source, i) in sources"
      :key="i"
      class="citation"
      :href="researchApi.pdfUrl(source.document_id)"
      target="_blank"
      rel="noopener"
    >
      <span class="citation-title">{{ source.document_title }}, p. {{ source.page_number }}</span>
      <SimilarityRule :value="source.similarity_score" :label="source.similarity_score.toFixed(2)" size="sm" />
    </a>
  </div>
</template>

<style scoped>
.citations {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--divider);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-4);
}

.citations-label {
  font-size: 11px;
  color: var(--text-faint);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.citation {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  text-decoration: none;
  min-width: 140px;
}

.citation-title {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.citation:hover .citation-title {
  color: var(--accent);
}
</style>
