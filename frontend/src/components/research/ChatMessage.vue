<script setup>
import CitationFooter from "./CitationFooter.vue";
import { scenarioCaption } from "@/utils/scenario";

const props = defineProps({ exchange: { type: Object, required: true } });
</script>

<template>
  <article class="exchange">
    <p class="query">{{ exchange.query_text }}</p>

    <div v-if="exchange.pending" class="pending">Thinking…</div>

    <template v-else>
      <p class="scenario-caption">{{ scenarioCaption(exchange.scenario, exchange.answer_mode) }}</p>
      <div class="answer">{{ exchange.response_text }}</div>
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

.pending {
  font-family: var(--font-serif);
  font-size: 16px;
  font-style: italic;
  color: var(--text-faint);
}
</style>
