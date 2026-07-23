import { api } from "./client";
import { streamSse } from "./sse";

export const researchApi = {
  // ISSUE-015 (AGENT_TASKS.md): POST /research/query now streams its
  // answer as Server-Sent Events - see app/routers/research.py's
  // submit_query docstring for the meta/chunk/done/error event sequence.
  // `onEvent({ event, data })` is called once per SSE message as it
  // arrives; the returned promise resolves once the stream ends.
  streamQuery: (queryText, answerMode, onEvent, options) =>
    streamSse("/api/research/query", { query_text: queryText, answer_mode: answerMode }, onEvent, options),
  getHistory: (limit = 50) => api.get(`/research/history?limit=${limit}`),
  pdfUrl: (documentId) => `/api/research/documents/${documentId}/pdf`,
};
