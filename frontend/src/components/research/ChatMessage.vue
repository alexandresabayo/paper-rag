<script setup>
import { computed } from "vue";
import CitationFooter from "./CitationFooter.vue";
import { scenarioCaption } from "@/utils/scenario";
import { renderMarkdown } from "@/utils/markdown";

const props = defineProps({ exchange: { type: Object, required: true } });
defineEmits(["retry"]);

// The streaming cursor is baked into the rendered HTML itself (see
// renderMarkdown's docstring), not a separate template element - a
// separate sibling span can't reliably sit at "the end of the last
// Markdown element" once that element could be a paragraph, a list
// item, a heading, etc.
const renderedAnswer = computed(() => renderMarkdown(props.exchange.response_text, props.exchange.streaming));
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
      <div class="answer" v-html="renderedAnswer"></div>
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
}

/* Content below arrives via v-html (rendered Markdown), so scoped
   styles need :deep() to reach it - see ChatMessage.vue's <script>. */
.answer :deep(p) {
  margin: 0 0 0.9em;
}

.answer :deep(p:last-child) {
  margin-bottom: 0;
}

.answer :deep(h1),
.answer :deep(h2),
.answer :deep(h3),
.answer :deep(h4) {
  font-family: var(--font-sans);
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
  margin: 1.1em 0 0.5em;
}

.answer :deep(h1:first-child),
.answer :deep(h2:first-child),
.answer :deep(h3:first-child),
.answer :deep(h4:first-child) {
  margin-top: 0;
}

.answer :deep(h1) {
  font-size: 1.25em;
}
.answer :deep(h2) {
  font-size: 1.15em;
}
.answer :deep(h3),
.answer :deep(h4) {
  font-size: 1.05em;
}

.answer :deep(strong) {
  font-weight: 600;
  color: var(--text);
}

.answer :deep(ul),
.answer :deep(ol) {
  margin: 0 0 0.9em;
  padding-left: 1.3em;
}

.answer :deep(li) {
  margin: 0.3em 0;
}

.answer :deep(li > p) {
  margin: 0;
}

.answer :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background: var(--bg-sunken);
  border: 1px solid var(--divider);
  border-radius: 3px;
  padding: 0.1em 0.4em;
}

.answer :deep(pre) {
  background: var(--bg-sunken);
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  overflow-x: auto;
  margin: 0 0 0.9em;
}

.answer :deep(pre code) {
  background: none;
  border: none;
  padding: 0;
  font-size: 0.85em;
}

.answer :deep(blockquote) {
  margin: 0 0 0.9em;
  padding-left: var(--space-3);
  border-left: 2px solid var(--divider-strong);
  color: var(--text-muted);
}

.answer :deep(a) {
  color: var(--accent);
}

.answer :deep(hr) {
  border: none;
  border-top: 1px solid var(--divider);
  margin: 1em 0;
}

.answer :deep(table) {
  border-collapse: collapse;
  margin: 0 0 0.9em;
  font-size: 0.92em;
}

.answer :deep(th),
.answer :deep(td) {
  border: 1px solid var(--divider);
  padding: var(--space-1) var(--space-2);
  text-align: left;
}

.answer :deep(.md-cursor) {
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
