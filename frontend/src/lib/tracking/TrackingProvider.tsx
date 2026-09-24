"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { endpoints } from "@/lib/api/client";

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
 * Buffers events and flushes to POST /api/v1/collector/events/batch every
 * 10 seconds or 20 events. Idle detection via heartbeat gaps arrives in Phase 8.
 */
export function TrackingProvider({ children }: { children: React.ReactNode }) {
  const queue = useRef<TrackEvent[]>([]);
  const sessionId = useRef<string | null>(null);
  const [flushing, setFlushing] = useState(false);

  const flush = useCallback(async () => {
    if (flushing || queue.current.length === 0) return;
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

  useEffect(() => {
    const interval = setInterval(() => void flush(), FLUSH_INTERVAL_MS);
    const onUnload = () => void flush();
    window.addEventListener("beforeunload", onUnload);
    return () => {
      clearInterval(interval);
      window.removeEventListener("beforeunload", onUnload);
      void flush();
    };
  }, [flush]);

  return <TrackingContext.Provider value={{ track }}>{children}</TrackingContext.Provider>;
}
