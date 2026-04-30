<script setup>
/**
 * A quiet horizontal "rule" - a filled track from 0 to `value` (0..1).
 * This is the one recurring instrument in the whole app: a similarity
 * score in Research and a page-progress bar in Ingestion are the same
 * shape, just relabeled, per the PRD's own phrase "the top of a
 * similarity-score scale."
 */
const props = defineProps({
  value: { type: Number, required: true }, // 0..1
  label: { type: String, default: "" },
  tone: { type: String, default: "accent" }, // 'accent' | 'done' | 'failed' | 'pending'
  size: { type: String, default: "sm" }, // 'sm' | 'md'
});

const toneVar = {
  accent: "var(--accent)",
  done: "var(--status-done)",
  failed: "var(--status-failed)",
  pending: "var(--status-pending)",
}[props.tone];
</script>

<template>
  <div class="rule-wrap" :class="size">
    <div class="rule-track">
      <div class="rule-fill" :style="{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: toneVar }" />
    </div>
    <span v-if="label" class="rule-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.rule-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.rule-track {
  flex: 1;
  min-width: 32px;
  background: var(--divider);
  border-radius: 2px;
  overflow: hidden;
}

.rule-wrap.sm .rule-track {
  height: 2px;
}
.rule-wrap.md .rule-track {
  height: 4px;
}

.rule-fill {
  height: 100%;
  transition: width 0.4s ease;
}

.rule-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}
</style>
