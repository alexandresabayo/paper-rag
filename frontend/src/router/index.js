import { createRouter, createWebHistory } from "vue-router";

const routes = [
  {
    path: "/",
    redirect: "/research",
  },
  {
    path: "/research",
    name: "research",
    component: () => import("@/views/research/ResearchView.vue"),
  },
  {
    path: "/ingestion",
    name: "ingestion",
    component: () => import("@/views/ingestion/IngestionDashboard.vue"),
  },
  {
    path: "/ingestion/documents/:documentId",
    name: "document-detail",
    component: () => import("@/views/ingestion/DocumentDetailView.vue"),
    props: true,
  },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});
