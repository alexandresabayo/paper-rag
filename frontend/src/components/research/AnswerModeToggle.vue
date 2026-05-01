<script setup>
defineProps({ modelValue: { type: String, required: true } });
defineEmits(["update:modelValue"]);
</script>

<template>
  <div class="toggle" role="radiogroup" aria-label="Answer mode">
    <button
      type="button"
      class="option"
      :class="{ active: modelValue === 'full_rag' }"
      role="radio"
      :aria-checked="modelValue === 'full_rag'"
      @click="$emit('update:modelValue', 'full_rag')"
    >
      Full RAG
    </button>
    <button
      type="button"
      class="option"
      :class="{ active: modelValue === 'direct_model' }"
      role="radio"
      :aria-checked="modelValue === 'direct_model'"
      @click="$emit('update:modelValue', 'direct_model')"
    >
      Direct model
    </button>
  </div>
</template>

<style scoped>
.toggle {
  display: inline-flex;
  border: 1px solid var(--divider-strong);
  border-radius: var(--radius-md);
  padding: 2px;
  gap: 2px;
}

.option {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 500;
  padding: 5px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.option:hover {
  color: var(--text);
}

.option.active {
  background: var(--accent-dim);
  color: var(--accent);
}
</style>
