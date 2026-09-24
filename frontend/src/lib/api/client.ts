import axios from "axios";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

/** Phase 3: attach JWT from storage to every request. */
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem("cm_access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const endpoints = {
  fes: {
    current: () => api.get("/api/v1/fes/current"),
    history: () => api.get("/api/v1/fes/history"),
    submetrics: () => api.get("/api/v1/fes/submetrics"),
  },
  recommendations: {
    list: () => api.get("/api/v1/recommendations/"),
    accept: (id: string) => api.post(`/api/v1/recommendations/${id}/accept`),
    reject: (id: string) => api.post(`/api/v1/recommendations/${id}/reject`),
    explain: (id: string) => api.get(`/api/v1/recommendations/${id}/explain`),
  },
  careers: {
    pathways: () => api.get("/api/v1/careers/pathways"),
    predictions: () => api.get("/api/v1/careers/predictions"),
  },
  collector: {
    startSession: () => api.post("/api/v1/collector/sessions/start"),
    endSession: (id: string) => api.post(`/api/v1/collector/sessions/${id}/end`),
    events: (batch: unknown[]) => api.post("/api/v1/collector/events/batch", { events: batch }),
  },
  llm: {
    chat: (message: string) => api.post("/api/v1/llm/chat", { message }),
  },
};
