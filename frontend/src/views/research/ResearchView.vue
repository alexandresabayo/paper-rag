<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
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
const chatInputRef = ref(null);

// ISSUE-019 (AGENT_TASKS.md): up-arrow-to-recall reads the most recent
// *submitted* query, not merely the last item in `exchanges` verbatim -
// same source either way today, but keeping it as its own computed
// means a future change (e.g. filtering out failed exchanges) only
// needs to change one place.
const lastQueryText = computed(() => {
  const last = exchanges.value[exchanges.value.length - 1];
  return last ? last.query_text : "";
});

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

onMounted(() => {
  loadHistory();
  window.addEventListener("keydown", onGlobalKeydown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", onGlobalKeydown);
});

function isTypingTarget(el) {
  if (!el) return false;
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable;
}

function onGlobalKeydown(event) {
  // '/' focuses the chat input from anywhere on the page (ISSUE-019,
  // AGENT_TASKS.md) - but not while already typing somewhere else, or
  // it would hijack a literal '/' the person meant to type.
  if (event.key === "/" && !isTypingTarget(document.activeElement)) {
    event.preventDefault();
    chatInputRef.value?.focus();
  }
}

async function ask(queryText) {
  // reactive() here, not a plain object literal, is load-bearing (bug
  // fix, predates the ISSUE-015/018/019 work above): `submitExchange`
  // and `retryExchange` mutate this `exchange` object directly via the
  // closure variable/parameter, not by re-reading it through
  // `exchanges.value[i]`. Vue only triggers a re-render when a mutation
  // goes *through* a reactive proxy - if `exchange` were a plain object,
  // pushing it into `exchanges.value` (itself reactive) does NOT retroactively
  // make this specific closure reference reactive; only reads made
  // through the array's own proxy would see live updates. In practice
  // that showed up as the answer staying stuck on "Thinking…"
  // indefinitely, even once generation had actually finished (visible
  // in the History sidebar, which re-renders correctly because
  // `loadHistory()` reassigns `historyItems.value` wholesale - a
  // genuinely reactive operation, unlike mutating a field on an object
  // already sitting inside a reactive array). Wrapping the object in
  // `reactive()` at creation makes the closure variable *itself* the
  // proxy, so every later mutation - from any function that captured
  // this same reference - correctly notifies the UI.
  const exchange = reactive({
    query_text: queryText,
    answer_mode: answerMode.value,
    pending: true,
    streaming: false,
    error: false,
    errorMessage: null,
    response_text: "",
    scenario: null,
    sources: [],
  });
  exchanges.value.push(exchange);
  scrollToBottom();
  await submitExchange(exchange);
}

async function submitExchange(exchange) {
  exchange.pending = true;
  exchange.streaming = false;
  exchange.error = false;
  exchange.errorMessage = null;
  exchange.response_text = "";
  exchange.scenario = null;
  exchange.sources = [];
  submitting.value = true;
  scrollToBottom();

  try {
    await researchApi.streamQuery(exchange.query_text, exchange.answer_mode, (message) => {
      if (message.event === "meta") {
        // Retrieval + scenario classification already happened server-side
        // by this point (ISSUE-015, AGENT_TASKS.md) - show the citations
        // right away rather than waiting for the answer text to finish.
        exchange.scenario = message.data.scenario;
        exchange.sources = message.data.sources;
        exchange.pending = false;
        exchange.streaming = true;
      } else if (message.event === "chunk") {
        exchange.response_text += message.data.text;
        scrollToBottom();
      } else if (message.event === "done") {
        exchange.response_text = message.data.response_text; // authoritative, not just our own concatenation
        exchange.streaming = false;
        loadHistory();
      } else if (message.event === "error") {
        exchange.error = true;
        exchange.errorMessage = message.data.message;
        exchange.streaming = false;
      }
    });
  } catch (err) {
    exchange.error = true;
    exchange.errorMessage = err.message;
  } finally {
    exchange.pending = false;
    exchange.streaming = false;
    submitting.value = false;
    scrollToBottom();
  }
}

function retryExchange(exchange) {
  submitExchange(exchange);
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    feedRef.value?.scrollTo({ top: feedRef.value.scrollHeight, behavior: "smooth" });
  });
}

function selectHistoryItem(item) {
  exchanges.value = [
    reactive({
      query_text: item.query_text,
      response_text: item.response_text,
      answer_mode: item.answer_mode,
      scenario: item.scenario,
      sources: [],
      pending: false,
      streaming: false,
      error: false,
      errorMessage: null,
    }),
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
        <ChatMessage v-for="(exchange, i) in exchanges" :key="i" :exchange="exchange" @retry="retryExchange" />
      </div>

      <ChatInput
        ref="chatInputRef"
        v-model:answer-mode="answerMode"
        :disabled="submitting"
        :last-query-text="lastQueryText"
        @submit="ask"
      />
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