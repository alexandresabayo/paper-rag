<script setup>
import { reactive, watch } from "vue";

const props = defineProps({ document: { type: Object, required: true } });
const emit = defineEmits(["save"]);

const form = reactive({
  doc_type: "",
  authors: "",
  year: "",
  title: "",
  venue: "",
  doi: "",
  acronym: "",
});

function loadFromDocument(doc) {
  form.doc_type = doc.doc_type || "";
  form.authors = (doc.authors || []).join(", ");
  form.year = doc.year || "";
  form.title = doc.title || "";
  form.venue = doc.venue || "";
  form.doi = doc.doi || "";
  form.acronym = doc.acronym || "";
}

watch(() => props.document, loadFromDocument, { immediate: true });

function submit() {
  emit("save", {
    doc_type: form.doc_type || null,
    authors: form.authors
      ? form.authors.split(",").map((a) => a.trim()).filter(Boolean)
      : [],
    year: form.year || null,
    title: form.title || null,
    venue: form.venue || null,
    doi: form.doi || null,
    acronym: form.acronym || null,
  });
}
</script>

<template>
  <form class="metadata-form" @submit.prevent="submit">
    <div class="field">
      <label>Title</label>
      <input v-model="form.title" type="text" placeholder="N/A" />
    </div>
    <div class="field">
      <label>Authors <span class="hint">(comma-separated)</span></label>
      <input v-model="form.authors" type="text" placeholder="N/A" />
    </div>
    <div class="row">
      <div class="field">
        <label>Year</label>
        <input v-model="form.year" type="text" placeholder="N/A" />
      </div>
      <div class="field">
        <label>Doc type</label>
        <input v-model="form.doc_type" type="text" placeholder="N/A" />
      </div>
    </div>
    <div class="field">
      <label>Venue</label>
      <input v-model="form.venue" type="text" placeholder="N/A" />
    </div>
    <div class="row">
      <div class="field">
        <label>DOI</label>
        <input v-model="form.doi" type="text" placeholder="N/A" />
      </div>
      <div class="field">
        <label>Acronym</label>
        <input v-model="form.acronym" type="text" placeholder="N/A" />
      </div>
    </div>
    <button class="save-btn" type="submit">Save corrections</button>
  </form>
</template>

<style scoped>
.metadata-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.row {
  display: flex;
  gap: var(--space-3);
}

.row .field {
  flex: 1;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

label {
  font-size: 11px;
  color: var(--text-faint);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.hint {
  text-transform: none;
  letter-spacing: 0;
}

input {
  background: var(--bg-sunken);
  border: 1px solid var(--divider-strong);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  color: var(--text);
  font-size: 13px;
  font-family: var(--font-sans);
}

input:focus {
  outline: none;
  border-color: var(--accent);
}

.save-btn {
  align-self: flex-start;
  margin-top: var(--space-2);
  background: var(--accent-dim);
  color: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-4);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.save-btn:hover {
  background: var(--accent-dim-strong);
}
</style>
