<script setup>
/**
 * ISSUE-021 (AGENT_TASKS.md): `GET /api/ingestion/reports/quality`
 * already returns `failed_documents` / `failed_pages` /
 * `na_metadata_documents` arrays (app/services/quality.py) - this is
 * the first thing in the frontend that actually renders them, rather
 * than just the summary counts in the quality strip above it.
 *
 * Each section is closed by default and expands on click - matching
 * the Design section's "understated, no badge walls" instruction: the
 * counts already live in the quality strip, so this is a drill-down
 * for detail, not a second copy of the same numbers sitting open by
 * default.
 */
import { ref } from "vue";
import { useRouter } from "vue-router";

const props = defineProps({ quality: { type: Object, required: true } });
const router = useRouter();

const openSection = ref(null); // 'documents' | 'pages' | 'metadata' | null

function toggle(section) {
  openSection.value = openSection.value === section ? null : section;
}

function openDocument(documentId) {
  router.push({ name: "document-detail", params: { documentId } });
}

function shortId(documentId) {
  return `${documentId.slice(0, 10)}…`;
}
</script>

<template>
  <section
    v-if="quality.failed_documents.length || quality.failed_pages.length || quality.na_metadata_documents.length"
    class="drilldown"
  >
    <div v-if="quality.failed_documents.length" class="drilldown-section">
      <button class="drilldown-toggle" type="button" @click="toggle('documents')">
        <span class="caret" :class="{ open: openSection === 'documents' }">›</span>
        {{ quality.failed_documents.length }} failed document{{ quality.failed_documents.length === 1 ? "" : "s" }}
      </button>
      <ul v-if="openSection === 'documents'" class="drilldown-list">
        <li v-for="d in quality.failed_documents" :key="d.id" class="drilldown-item" @click="openDocument(d.id)">
          <span class="item-name">{{ d.file_name }}</span>
          <span class="item-detail">{{ d.last_error || "—" }}</span>
        </li>
      </ul>
    </div>

    <div v-if="quality.failed_pages.length" class="drilldown-section">
      <button class="drilldown-toggle" type="button" @click="toggle('pages')">
        <span class="caret" :class="{ open: openSection === 'pages' }">›</span>
        {{ quality.failed_pages.length }} failed page{{ quality.failed_pages.length === 1 ? "" : "s" }}
      </button>
      <ul v-if="openSection === 'pages'" class="drilldown-list">
        <li
          v-for="(p, i) in quality.failed_pages"
          :key="`${p.document_id}:${p.page_number}:${i}`"
          class="drilldown-item"
          @click="openDocument(p.document_id)"
        >
          <span class="item-name mono">p.{{ p.page_number }} · {{ shortId(p.document_id) }}</span>
          <span class="item-detail">{{ p.error_message || "—" }}</span>
        </li>
      </ul>
    </div>

    <div v-if="quality.na_metadata_documents.length" class="drilldown-section">
      <button class="drilldown-toggle" type="button" @click="toggle('metadata')">
        <span class="caret" :class="{ open: openSection === 'metadata' }">›</span>
        {{ quality.na_metadata_documents.length }} document{{ quality.na_metadata_documents.length === 1 ? "" : "s" }}
        with N/A metadata
      </button>
      <ul v-if="openSection === 'metadata'" class="drilldown-list">
        <li v-for="d in quality.na_metadata_documents" :key="d.id" class="drilldown-item" @click="openDocument(d.id)">
          <span class="item-name">{{ d.file_name }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.drilldown {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--divider);
}

.drilldown-section + .drilldown-section {
  border-top: 1px solid var(--divider);
  padding-top: var(--space-1);
}

.drilldown-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  background: none;
  border: none;
  text-align: left;
  color: var(--status-failed);
  font-size: 12px;
  font-family: var(--font-sans);
  padding: var(--space-1) 0;
  cursor: pointer;
}

.drilldown-toggle:hover {
  color: var(--text);
}

.caret {
  display: inline-block;
  color: var(--text-faint);
  transition: transform 0.15s ease;
}

.caret.open {
  transform: rotate(90deg);
}

.drilldown-list {
  list-style: none;
  margin: 0;
  padding: 0 0 var(--space-1) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 220px;
  overflow-y: auto;
}

.drilldown-item {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.drilldown-item:hover {
  background: var(--bg-hover);
}

.item-name {
  flex: none;
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.item-name.mono {
  font-family: var(--font-mono);
}

.item-detail {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
