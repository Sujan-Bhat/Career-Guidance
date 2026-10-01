"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useSyncExternalStore,
} from "react";
import { endpoints, getAuthVersion, isLoggedIn, subscribeAuth } from "@/lib/api/client";

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
    | "heartbeat"
    | "recommendation_decision";
  resource_id?: string;
  metadata?: Record<string, unknown>;
  timestamp: string;
};

const FLUSH_INTERVAL_MS = 10_000;
const FLUSH_THRESHOLD = 20;

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type TrackingContextValue = {
  track: (type: TrackEvent["type"], payload?: Omit<TrackEvent, "type" | "timestamp">) => void;
};

const TrackingContext = createContext<TrackingContextValue>({ track: () => {} });

export function useTracking() {
  return useContext(TrackingContext);
}

/**
 * Client half of the Behavioural Data Collector (paper Sec. V).
 * Opens ONE server-side session when logged in, buffers events, flushes to
 * POST /api/v1/collector/events/batch every 10s / 20 events, and closes the
 * session on unload via a keepalive fetch that carries the final event batch
 * (sendBeacon can't send the Authorization header).
 *
 * Session lifecycle notes (bug fixes):
 *  - `flush`/`track` identities stay stable (flushing flag lives in a ref),
 *    so the mount effect runs exactly once per auth change — the tracked
 *    session is opened once and closed once, not restarted on every flush.
 *  - The effect re-runs whenever `getAuthVersion()` changes (login/logout).
 *    Previously it ran exactly once on mount and early-returned while logged
 *    out, so logging in without a full page reload left `sessionId` null
 *    forever: flush() no-oped, no interval or beforeunload listener was ever
 *    registered, and every subsequent event queued until the tab closed.
 *  - A `startSession` that resolves after the effect was cleaned up (React
 *    StrictMode double-mount, or logout racing the request) is closed
 *    immediately instead of being orphaned as a session that never ends.
 *  - On unload / teardown the buffered batch is delivered in the same
 *    keepalive request that ends the session, using the bearer token the
 *    session was opened with so logout can still close it server-side.
 */
export function TrackingProvider({ children }: { children: React.ReactNode }) {
  const queue = useRef<TrackEvent[]>([]);
  const sessionId = useRef<string | null>(null);
  const sessionToken = useRef<string | null>(null);
  const flushing = useRef(false);

  const authVersion = useSyncExternalStore(subscribeAuth, getAuthVersion, getAuthVersion);

  /** Deliver queued events with keepalive so they survive navigation. */
  const sendEvents = useCallback(async (batch: TrackEvent[], token: string | null) => {
    try {
      await fetch(`${API_BASE}/api/v1/collector/events/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        // session_id stated explicitly: server-side "newest active session"
        // resolution is only a fallback, and events must never land in the
        // wrong (e.g. duplicate-start orphan) session
        body: JSON.stringify({ session_id: sessionId.current, events: batch }),
        keepalive: true,
      });
    } catch {
      // dropped events are acceptable at prototype fidelity
    }
  }, []);

  const flush = useCallback(async () => {
    if (flushing.current || queue.current.length === 0 || !sessionId.current) return;
    flushing.current = true;
    const batch = queue.current.splice(0, queue.current.length);
    try {
      await sendEvents(batch, window.localStorage.getItem("cm_access_token"));
    } finally {
      flushing.current = false;
    }
  }, [sendEvents]);

  const track = useCallback<TrackingContextValue["track"]>((type, payload) => {
    queue.current.push({ type, ...payload, timestamp: new Date().toISOString() });
    if (queue.current.length >= FLUSH_THRESHOLD) void flush();
  }, [flush]);

  // open a session on mount/auth change; close it on unload or auth change
  useEffect(() => {
    if (!isLoggedIn()) return;

    let cancelled = false;
    endpoints.collector
      .startSession()
      .then(({ data }) => {
        if (cancelled) {
          // effect already tore down: close the session we just opened so it
          // doesn't linger as "active" forever (StrictMode double-mount, or a
          // logout that raced this request)
          void endpoints.collector.endSession(data.session_id).catch(() => {});
          return;
        }
        sessionId.current = data.session_id;
        sessionToken.current = window.localStorage.getItem("cm_access_token");
      })
      .catch(() => {});

    const endSession = (finalBatch: TrackEvent[], token: string | null) => {
      const id = sessionId.current;
      if (!id) return;
      // Single keepalive request carries the last batch AND closes the
      // session, so ordering is preserved and nothing is lost on unload.
      fetch(`${API_BASE}/api/v1/collector/sessions/${id}/end`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(finalBatch.length ? { events: finalBatch } : {}),
        keepalive: true,
      }).catch(() => {});
    };

    const onUnload = () => {
      const finalBatch = queue.current.splice(0, queue.current.length);
      endSession(finalBatch, sessionToken.current);
    };
    window.addEventListener("beforeunload", onUnload);

    const interval = setInterval(() => void flush(), FLUSH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
      window.removeEventListener("beforeunload", onUnload);
      // Route-level unmount / logout: flush what we have and close the
      // session through the API. beforeunload covers real tab closes.
      const finalBatch = queue.current.splice(0, queue.current.length);
      if (finalBatch.length && sessionId.current) {
        void sendEvents(finalBatch, sessionToken.current);
      }
      if (sessionId.current) endSession([], sessionToken.current);
      sessionId.current = null;
      sessionToken.current = null;
      flushing.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authVersion]);

  return <TrackingContext.Provider value={{ track }}>{children}</TrackingContext.Provider>;
}
