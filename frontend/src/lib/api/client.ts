import axios from "axios";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

/** Attach the JWT to every request. */
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem("cm_access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** One silent refresh-and-retry on 401 (auth endpoints excluded). */
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      !original._retried &&
      !original.url.includes("/accounts/login") &&
      !original.url.includes("/accounts/register")
    ) {
      original._retried = true;
      const refresh = window.localStorage.getItem("cm_refresh_token");
      if (refresh) {
        try {
          const { data } = await axios.post(
            `${api.defaults.baseURL}/api/v1/accounts/refresh`,
            { refresh }
          );
          window.localStorage.setItem("cm_access_token", data.access);
          return api(original);
        } catch {
          window.localStorage.removeItem("cm_access_token");
          window.localStorage.removeItem("cm_refresh_token");
        }
      }
    }
    throw error;
  }
);

export function storeTokens(access: string, refresh: string) {
  window.localStorage.setItem("cm_access_token", access);
  window.localStorage.setItem("cm_refresh_token", refresh);
}

export function clearTokens() {
  window.localStorage.removeItem("cm_access_token");
  window.localStorage.removeItem("cm_refresh_token");
}

export function isLoggedIn(): boolean {
  return typeof window !== "undefined" && !!window.localStorage.getItem("cm_access_token");
}

export const endpoints = {
  auth: {
    register: (payload: { email: string; full_name: string; password: string; programme?: string }) =>
      api.post("/api/v1/accounts/register", payload),
    login: (email: string, password: string) =>
      api.post("/api/v1/accounts/login", { email, password }),
    me: () => api.get("/api/v1/accounts/me"),
  },
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
  courses: {
    quizAttempt: (quizId: string, payload: { item_id: string; correct: boolean }) =>
      api.post(`/api/v1/courses/quizzes/${quizId}/attempt`, payload),
  },
  llm: {
    chat: (message: string) => api.post("/api/v1/llm/chat", { message }),
  },
};
