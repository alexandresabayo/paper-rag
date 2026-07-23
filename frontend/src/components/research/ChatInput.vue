<script setup>
import { ref } from "vue";
import AnswerModeToggle from "./AnswerModeToggle.vue";

const props = defineProps({
  answerMode: { type: String, required: true },
  disabled: { type: Boolean, default: false },
  lastQueryText: { type: String, default: "" },
});
const emit = defineEmits(["update:answerMode", "submit"]);

const text = ref("");
const textareaRef = ref(null);

function submit() {
  const trimmed = text.value.trim();
  if (!trimmed || props.disabled) return;
  emit("submit", trimmed);
  text.value = "";
}

function onKeydown(event) {
  // Cmd/Ctrl+Enter always submits, regardless of Shift - an explicit,
  // unambiguous alternate to plain Enter for anyone used to that
  // convention from other chat apps (ISSUE-019, AGENT_TASKS.md).
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    submit();
    return;
  }
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
    return;
  }
  // Up-arrow, on an empty input, recalls the last submitted query so it
  // can be edited and resent - only when empty, so it never clobbers
  // something the person is already typing or interferes with normal
  // in-textarea cursor movement once there's multi-line content.
  if (event.key === "ArrowUp" && text.value === "" && props.lastQueryText) {
    event.preventDefault();
    text.value = props.lastQueryText;
  }
}

defineExpose({
  focus: () => textareaRef.value?.focus(),
});
</script>

<template>
  <div class="input-bar">
    <div class="input-row">
      <textarea
        ref="textareaRef"
        v-model="text"
        class="input-field"
        rows="1"
        placeholder="Ask about your document corpus…"
        :disabled="disabled"
        @keydown="onKeydown"
      />
      <button class="send-button" type="button" :disabled="disabled || !text.trim()" @click="submit">Ask</button>
    </div>
    <div class="input-footer">
      <AnswerModeToggle :model-value="answerMode" @update:model-value="(v) => emit('update:answerMode', v)" />
      <span class="hint">Enter · ⌘/Ctrl+Enter to send · Shift+Enter for a new line · ↑ to recall · / to focus</span>
    </div>
  </div>
</template>

<style scoped>
.input-bar {
  border-top: 1px solid var(--divider);
  background: var(--bg-sunken);
  padding: var(--space-4) var(--space-5) var(--space-3);
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: var(--space-3);
  max-width: 720px;
  margin: 0 auto;
}

.input-field {
  flex: 1;
  resize: none;
  background: transparent;
  border: none;
  color: var(--text);
  font-family: var(--font-serif);
  font-size: 16px;
  line-height: 1.5;
  padding: var(--space-2) 0;
  max-height: 200px;
}

.input-field::placeholder {
  color: var(--text-faint);
}

.input-field:focus {
  outline: none;
}

.send-button {
  flex: none;
  background: var(--accent-dim);
  color: var(--accent);
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  padding: var(--space-2) var(--space-4);
  cursor: pointer;
  transition: background 0.15s ease;
}

.send-button:hover:not(:disabled) {
  background: var(--accent-dim-strong);
}

.send-button:disabled {
  color: var(--text-faint);
  background: transparent;
  cursor: default;
}

.input-footer {
  max-width: 720px;
  margin: var(--space-2) auto 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hint {
  font-size: 11px;
  color: var(--text-faint);
}
</style>
