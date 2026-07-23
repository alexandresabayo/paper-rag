<script setup>
import CitationFooter from "./CitationFooter.vue";
import { scenarioCaption } from "@/utils/scenario";

const props = defineProps({ exchange: { type: Object, required: true } });
defineEmits(["retry"]);
</script>

<template>
  <article class="exchange">
    <p class="query">{{ exchange.query_text }}</p>

    <div v-if="exchange.pending" class="pending">Thinking…</div>

    <div v-else-if="exchange.error" class="error-card" role="alert">
      <p class="error-title">Couldn't get a response</p>
      <p class="error-detail">{{ exchange.errorMessage }}</p>
      <button class="retry-button" type="button" @click="$emit('retry', exchange)">Retry</button>
    </div>

    <template v-else>
      <!-- Retrieval + scenario classification already finished before the
           first chunk arrives (ISSUE-015, AGENT_TASKS.md), so this and the
           citation footer render immediately - only the answer text below
           streams in progressively. -->
      <p class="scenario-caption">{{ scenarioCaption(exchange.scenario, exchange.answer_mode) }}</p>
      <div class="answer">{{ exchange.response_text }}<span v-if="exchange.streaming" class="cursor" aria-hidden="true"></span></div>
      <CitationFooter :sources="exchange.sources || []" />
    </template>
  </article>
</template>

<style scoped>
.exchange {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-6) 0;
  border-bottom: 1px solid var(--divider);
}

.exchange:last-child {
  border-bottom: none;
}

.query {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
  margin: 0 0 var(--space-4);
}

.scenario-caption {
  font-family: var(--font-sans);
  font-size: 11px;
  font-style: italic;
  color: var(--text-faint);
  margin: 0 0 var(--space-3);
}

.answer {
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.7;
  color: var(--text);
  white-space: pre-wrap;
}

.cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  background: var(--accent);
  vertical-align: text-bottom;
  animation: cursor-blink 1s step-start infinite;
}

@keyframes cursor-blink {
  50% {
    opacity: 0;
  }
}

.pending {
  font-family: var(--font-serif);
  font-size: 16px;
  font-style: italic;
  color: var(--text-faint);
}

.error-card {
  border: 1px solid var(--status-failed);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  background: rgba(196, 102, 79, 0.08);
}

.error-title {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 500;
  color: var(--status-failed);
  margin: 0 0 var(--space-1);
}

.error-detail {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 var(--space-3);
  word-break: break-word;
}

.retry-button {
  background: transparent;
  border: 1px solid var(--status-failed);
  color: var(--status-failed);
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  padding: var(--space-1) var(--space-3);
  cursor: pointer;
  transition: background 0.15s ease;
}

.retry-button:hover {
  background: rgba(196, 102, 79, 0.14);
}
</style>
