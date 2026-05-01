<script setup>
import { onMounted, ref } from "vue";
import HistorySidebar from "@/components/research/HistorySidebar.vue";
import ChatMessage from "@/components/research/ChatMessage.vue";
import ChatInput from "@/components/research/ChatInput.vue";
import { researchApi } from "@/api/research";

const exchanges = ref([]);
const answerMode = ref("full_rag");
const historyItems = ref([]);
const historyLoading = ref(false);
const sidebarCollapsed = ref(false);
const submitting = ref(false);
const feedRef = ref(null);

async function loadHistory() {
  historyLoading.value = true;
  try {
    const { items } = await researchApi.getHistory();
    historyItems.value = items;
  } catch (err) {
    console.error("Failed to load history", err);
  } finally {
    historyLoading.value = false;
  }
}

onMounted(loadHistory);

async function ask(queryText) {
  const placeholder = { query_text: queryText, answer_mode: answerMode.value, pending: true };
  exchanges.value.push(placeholder);
  submitting.value = true;
  scrollToBottom();

  try {
    const result = await researchApi.submitQuery(queryText, answerMode.value);
    Object.assign(placeholder, result, { pending: false });
    loadHistory();
  } catch (err) {
    Object.assign(placeholder, {
      pending: false,
      response_text: `Something went wrong reaching the backend: ${err.message}`,
      sources: [],
      scenario: null,
    });
  } finally {
    submitting.value = false;
    scrollToBottom();
  }
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    feedRef.value?.scrollTo({ top: feedRef.value.scrollHeight, behavior: "smooth" });
  });
}

function selectHistoryItem(item) {
  exchanges.value = [
    {
      query_text: item.query_text,
      response_text: item.response_text,
      answer_mode: item.answer_mode,
      scenario: item.scenario,
      sources: [],
      pending: false,
    },
  ];
}
</script>

<template>
  <div class="research">
    <HistorySidebar
      :items="historyItems"
      :loading="historyLoading"
      :collapsed="sidebarCollapsed"
      @select="selectHistoryItem"
      @toggle-collapsed="sidebarCollapsed = !sidebarCollapsed"
    />

    <div class="chat-column">
      <div ref="feedRef" class="feed">
        <div v-if="!exchanges.length" class="empty-state">
          <p class="empty-title">Ask something about your document corpus.</p>
          <p class="empty-hint">
            Full RAG retrieves from ingested documents first; Direct model skips retrieval entirely.
          </p>
        </div>
        <ChatMessage v-for="(exchange, i) in exchanges" :key="i" :exchange="exchange" />
      </div>

      <ChatInput v-model:answer-mode="answerMode" :disabled="submitting" @submit="ask" />
    </div>
  </div>
</template>

<style scoped>
.research {
  display: flex;
  height: 100%;
}

.chat-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.feed {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) var(--space-5) var(--space-4);
}

.empty-state {
  max-width: 720px;
  margin: var(--space-8) auto 0;
  text-align: center;
}

.empty-title {
  font-family: var(--font-serif);
  font-size: 20px;
  color: var(--text);
  margin: 0 0 var(--space-2);
}

.empty-hint {
  font-size: 13px;
  color: var(--text-faint);
  margin: 0;
}
</style>
