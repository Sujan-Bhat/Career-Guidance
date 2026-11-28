import { api } from "@/lib/api/client";

let running = false;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((fn) => fn());

export function isJobRunning() {
  return running;
}

export function subscribeJob(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export async function runBackgroundJob<T>(
  endpoint: string,
  formData: FormData,
  storageKey: string
): Promise<T> {
  running = true;
  notify();
  try {
    const res = await api.post<T>(endpoint, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    window.sessionStorage.setItem(storageKey, JSON.stringify(res.data));
    return res.data;
  } finally {
    running = false;
    notify();
  }
}