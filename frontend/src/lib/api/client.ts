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
          clearTokens(); // notifies auth subscribers: the session is over
        }
      }
    }
    throw error;
  }
);

/**
 * Auth store.
 *
 * Login / logout are the only operations that bump `authVersion`: subscribers
 * (notably TrackingProvider) re-run their session lifecycle when it changes,
 * so logging in without a full page reload still opens a behavioural session.
 *
 * The 401 refresh interceptor below deliberately writes the rotated access
 * token straight to localStorage WITHOUT bumping the version — a refresh is
 * not a login, and notifying would tear down and reopen the session on every
 * token rotation.
 */
let authVersion = 0;
const authListeners = new Set<() => void>();

function notifyAuthChange() {
  authVersion += 1;
  authListeners.forEach((listener) => listener());
}

export function subscribeAuth(listener: () => void): () => void {
  authListeners.add(listener);
  return () => {
    authListeners.delete(listener);
  };
}

export function getAuthVersion(): number {
  return authVersion;
}

export function storeTokens(access: string, refresh: string) {
  window.localStorage.setItem("cm_access_token", access);
  window.localStorage.setItem("cm_refresh_token", refresh);
  notifyAuthChange();
}

export function clearTokens() {
  window.localStorage.removeItem("cm_access_token");
  window.localStorage.removeItem("cm_refresh_token");
  notifyAuthChange();
}

export function isLoggedIn(): boolean {
  return typeof window !== "undefined" && !!window.localStorage.getItem("cm_access_token");
}

export const endpoints = {
  auth: {
    register: (payload: {
      email: string;
      full_name: string;
      password: string;
      programme?: string;
      year_of_study?: number;
    }) => api.post("/api/v1/accounts/register", payload),
    login: (email: string, password: string) =>
      api.post("/api/v1/accounts/login", { email, password }),
    me: () => api.get("/api/v1/accounts/me"),
    updateMe: (payload: { full_name?: string; programme?: string; year_of_study?: number }) =>
      api.patch("/api/v1/accounts/me", payload),
  },
  fes: {
    current: () => api.get("/api/v1/fes/current"),
    /** FES + the five sub-metrics per session, oldest to newest (server caps `limit` at 200). */
    history: (limit?: number) =>
      api.get("/api/v1/fes/history", limit ? { params: { limit } } : undefined),
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
    list: () => api.get("/api/v1/courses/"),
    quizzes: () => api.get("/api/v1/courses/quizzes"),
    quiz: (id: string) => api.get(`/api/v1/courses/quizzes/${id}`),
    quizAttempt: (quizId: string, payload: { item_id: string; selected: number }) =>
      api.post(`/api/v1/courses/quizzes/${quizId}/attempt`, payload),
  },
  llm: {
    chat: (message: string) => api.post("/api/v1/llm/chat", { message }),
    quizGenerate: (payload: { skill: string; difficulty: number; n_items: number }) =>
      api.post("/api/v1/llm/quiz/generate", payload),
  },
};
