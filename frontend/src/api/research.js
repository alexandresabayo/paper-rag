import { api } from "./client";

export const researchApi = {
  submitQuery: (queryText, answerMode) => api.post("/research/query", { query_text: queryText, answer_mode: answerMode }),
  getHistory: (limit = 50) => api.get(`/research/history?limit=${limit}`),
  pdfUrl: (documentId) => `/api/research/documents/${documentId}/pdf`,
};
