"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { endpoints, isLoggedIn } from "@/lib/api/client";

export type TrackEvent = {
  type:
    | "page_view"
    | "resource_open"
    | "resource_close"
    | "resource_switch"
    | "task_start"
    | "task_complete"
    | "quiz_attempt"
    | "idle_start"
    | "idle_end"
    | "heartbeat";
  resource_id?: string;
  metadata?: Record<string, unknown>;
  timestamp: string;
};

const FLUSH_INTERVAL_MS = 10_000;
const FLUSH_THRESHOLD = 20;

type TrackingContextValue = {
  track: (type: TrackEvent["type"], payload?: Omit<TrackEvent, "type" | "timestamp">) => void;
};

const TrackingContext = createContext<TrackingContextValue>({ track: () => {} });

export function useTracking() {
  return useContext(TrackingContext);
}

/**
 * Client half of the Behavioural Data Collector (paper Sec. V).
 * Opens a server-side session on mount (when logged in), buffers events,
 * flushes to POST /api/v1/collector/events/batch every 10s / 20 events, and
 * closes the session on unload via fetch keepalive (sendBeacon can't send
 * the Authorization header).
 */
export function TrackingProvider({ children }: { children: React.ReactNode }) {
  const queue = useRef<TrackEvent[]>([]);
  const sessionId = useRef<string | null>(null);
  const [flushing, setFlushing] = useState(false);

  const flush = useCallback(async () => {
    if (flushing || queue.current.length === 0 || !sessionId.current) return;
    const batch = queue.current.splice(0, queue.current.length);
    setFlushing(true);
    try {
      await endpoints.collector.events(batch);
    } catch {
      // Phase 8: retry with exponential backoff; drop silently for now
    } finally {
      setFlushing(false);
    }
  }, [flushing]);

  const track = useCallback<TrackingContextValue["track"]>((type, payload) => {
    queue.current.push({ type, ...payload, timestamp: new Date().toISOString() });
    if (queue.current.length >= FLUSH_THRESHOLD) void flush();
  }, [flush]);

  // open a session on mount; close it on unload
  useEffect(() => {
    if (!isLoggedIn()) return;

    let cancelled = false;
    endpoints.collector
      .startSession()
      .then(({ data }) => {
        if (!cancelled) sessionId.current = data.session_id;
      })
      .catch(() => {});

    const onUnload = () => {
      void flush();
      const id = sessionId.current;
      if (!id) return;
      const token = window.localStorage.getItem("cm_access_token");
      fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/collector/sessions/${id}/end`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          keepalive: true,
        }
      ).catch(() => {});
    };
    window.addEventListener("beforeunload", onUnload);

    const interval = setInterval(() => void flush(), FLUSH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
      window.removeEventListener("beforeunload", onUnload);
      void flush();
      if (sessionId.current) void endpoints.collector.endSession(sessionId.current);
      sessionId.current = null;
    };
  }, [flush]);

  return <TrackingContext.Provider value={{ track }}>{children}</TrackingContext.Provider>;
}
