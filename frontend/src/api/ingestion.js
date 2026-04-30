import { api } from "./client";

export const ingestionApi = {
  listDocuments: () => api.get("/ingestion/documents"),
  getDocument: (documentId) => api.get(`/ingestion/documents/${documentId}`),
  uploadDocuments: (files) => {
    const formData = new FormData();
    for (const file of files) formData.append("files", file);
    return api.post("/ingestion/documents", formData);
  },
  retryDocument: (documentId) => api.post(`/ingestion/documents/${documentId}/retry`),
  updateMetadata: (documentId, fields) => api.patch(`/ingestion/documents/${documentId}/metadata`, fields),
  getQualityReport: () => api.get("/ingestion/reports/quality"),
};
