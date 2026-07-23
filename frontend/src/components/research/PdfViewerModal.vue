<script setup>
/**
 * Inline PDF viewer with page jump (ISSUE-017, AGENT_TASKS.md).
 *
 * Deliberately built on the browser's own PDF renderer (an <iframe> with
 * a `#page=N` URL fragment - a long-standing convention Chrome/Firefox/
 * Safari's built-in PDF viewers all honor) rather than bundling pdf.js.
 * The issue text says "consider an inline viewer (e.g. pdf.js)" - pdf.js
 * is one way to get there, not the requirement itself, and this gets the
 * same outcome (inline, jumps to the cited page) with far less surface
 * area: no worker-file bundling/version-matching concerns, and nothing
 * that depends on a CDN. The trade-off is less control over in-viewer
 * chrome (zoom/nav controls are the browser's own) - a real limitation
 * if a more custom viewer experience is wanted later, at which point
 * swapping in pdf.js here is a contained, one-component change.
 *
 * Requires the PDF endpoint to send `Content-Disposition: inline` (see
 * app/routers/research.py::serve_pdf) - otherwise the browser downloads
 * the file instead of rendering it inside the frame.
 */
import { onMounted, onUnmounted, ref } from "vue";
import { researchApi } from "@/api/research";

const props = defineProps({
  documentId: { type: String, required: true },
  documentTitle: { type: String, required: true },
  pageNumber: { type: Number, required: true },
});
const emit = defineEmits(["close"]);

const closeButtonRef = ref(null);

const baseUrl = researchApi.pdfUrl(props.documentId);
const iframeSrc = `${baseUrl}#page=${props.pageNumber}`;
const newTabUrl = iframeSrc;

function onKeydown(event) {
  if (event.key === "Escape") emit("close");
}

onMounted(() => {
  window.addEventListener("keydown", onKeydown);
  closeButtonRef.value?.focus();
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <Teleport to="body">
    <div class="scrim" @click.self="emit('close')">
      <div class="panel" role="dialog" aria-modal="true" :aria-label="`${documentTitle}, page ${pageNumber}`">
        <header class="panel-header">
          <div class="panel-heading">
            <span class="panel-title">{{ documentTitle }}</span>
            <span class="panel-page">p. {{ pageNumber }}</span>
          </div>
          <div class="panel-actions">
            <a class="open-new-tab" :href="newTabUrl" target="_blank" rel="noopener">Open in new tab ↗</a>
            <button ref="closeButtonRef" class="close-button" type="button" aria-label="Close" @click="emit('close')">
              ×
            </button>
          </div>
        </header>
        <iframe class="pdf-frame" :src="iframeSrc" :title="`${documentTitle}, page ${pageNumber}`" />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.scrim {
  position: fixed;
  inset: 0;
  background: rgba(15, 15, 14, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
  z-index: 100;
}

.panel {
  background: var(--bg-raised);
  border: 1px solid var(--divider-strong);
  border-radius: var(--radius-md);
  width: min(1000px, 100%);
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.panel-header {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--divider);
}

.panel-heading {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  min-width: 0;
}

.panel-title {
  font-family: var(--font-serif);
  font-size: 14px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.panel-page {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  flex: none;
}

.panel-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.open-new-tab {
  font-size: 12px;
  color: var(--text-muted);
  text-decoration: none;
  white-space: nowrap;
}

.open-new-tab:hover {
  color: var(--accent);
}

.close-button {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  padding: 0 var(--space-1);
}

.close-button:hover {
  color: var(--text);
}

.pdf-frame {
  flex: 1;
  border: none;
  background: #ffffff;
}
</style>
