<script setup>
import { ref } from "vue";

const emit = defineEmits(["upload"]);
const dragging = ref(false);
const inputRef = ref(null);

function handleFiles(fileList) {
  const files = Array.from(fileList).filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
  if (files.length) emit("upload", files);
}

function onDrop(event) {
  dragging.value = false;
  handleFiles(event.dataTransfer.files);
}

function onPick(event) {
  handleFiles(event.target.files);
  event.target.value = "";
}
</script>

<template>
  <div
    class="dropzone"
    :class="{ dragging }"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="onDrop"
    @click="inputRef.click()"
  >
    <p class="dropzone-text">Drop PDFs here, or click to browse</p>
    <p class="dropzone-hint">Batch upload supported — each file becomes its own document</p>
    <input ref="inputRef" type="file" accept="application/pdf" multiple hidden @change="onPick" />
  </div>
</template>

<style scoped>
.dropzone {
  border: 1px dashed var(--divider-strong);
  border-radius: var(--radius-md);
  padding: var(--space-6);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.dropzone:hover,
.dropzone.dragging {
  border-color: var(--accent);
  background: var(--accent-dim);
}

.dropzone-text {
  font-size: 14px;
  color: var(--text);
  margin: 0 0 var(--space-1);
}

.dropzone-hint {
  font-size: 12px;
  color: var(--text-faint);
  margin: 0;
}
</style>
