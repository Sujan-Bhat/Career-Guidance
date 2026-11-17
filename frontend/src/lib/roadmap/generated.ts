"use client";

import { useSyncExternalStore } from "react";

import { roadmapSchema, type Roadmap } from "@/types/roadmap";

/**
 * Store for AI-generated roadmaps.
 *
 * Generated roadmaps live in two places:
 *  - server (Mongo, per-student) — durable across devices; fetched on demand
 *  - this module — the client mirror, so the canvas/dashboard can resolve a
 *    generated slug synchronously like a seed roadmap
 *
 * Mirrors the defensive posture of `storage.ts`: zod-validated on read,
 * in-memory fallback when localStorage is unavailable/quota-exceeded/corrupt.
 * `getRoadmap()` in `registry.ts` consults this store after the seed data.
 */

const STORAGE_KEY = "cm_generated_roadmaps_v1";

type GeneratedMap = Record<string, Roadmap>;

const EMPTY: GeneratedMap = {};

let cache: GeneratedMap | null = null;
const listeners = new Set<() => void>();

function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null; // SSR / privacy mode
  }
}

function readAll(): GeneratedMap {
  const storage = getStorage();
  if (!storage) return EMPTY;
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (raw === null) return EMPTY;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return EMPTY;
    }
    const result: GeneratedMap = {};
    for (const [slug, value] of Object.entries(parsed as Record<string, unknown>)) {
      const roadmap = roadmapSchema.safeParse(value);
      // Drop entries that fail validation (corrupt/older shape) instead of
      // crashing the whole store.
      if (roadmap.success) result[slug] = roadmap.data;
    }
    return result;
  } catch {
    return EMPTY;
  }
}

function persist(state: GeneratedMap): void {
  const storage = getStorage();
  if (!storage) return;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // quota exceeded — keep serving from memory for this session
  }
}

function getState(): GeneratedMap {
  if (cache === null) cache = readAll();
  return cache;
}

function emit(): void {
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Drop the in-memory cache so the next read re-derives from storage.
 * Exists for tests (isolating cases without leaking module state); no
 * production call site needs it because the cache mirrors storage anyway.
 */
export function resetGeneratedStore(): void {
  cache = null;
}

/** Resolve a generated roadmap, or undefined (also on the server). */
export function getGeneratedRoadmap(slug: string): Roadmap | undefined {
  if (typeof window === "undefined") return undefined;
  return getState()[slug];
}

/** Save (or replace) a generated roadmap and notify subscribers. */
export function saveGeneratedRoadmap(roadmap: Roadmap): void {
  const parsed = roadmapSchema.safeParse(roadmap);
  if (!parsed.success) {
    // A roadmap that fails the schema must never reach the canvas.
    // eslint-disable-next-line no-console
    console.error("Refusing to save invalid generated roadmap", parsed.error.issues);
    return;
  }
  const state = getState();
  cache = { ...state, [parsed.data.slug]: parsed.data };
  persist(cache);
  emit();
}

/** Merge roadmaps fetched from the backend (no-op for ones we already have). */
export function mergeGeneratedRoadmaps(roadmaps: Roadmap[]): void {
  let changed = false;
  const next: GeneratedMap = { ...getState() };
  for (const roadmap of roadmaps) {
    const parsed = roadmapSchema.safeParse(roadmap);
    if (parsed.success && !next[parsed.data.slug]) {
      next[parsed.data.slug] = parsed.data;
      changed = true;
    }
  }
  if (changed) {
    cache = next;
    persist(cache);
    emit();
  }
}

/** Remove a generated roadmap from the client store and notify subscribers. */
export function removeGeneratedRoadmap(slug: string): void {
  const state = getState();
  if (slug in state) {
    const next = { ...state };
    delete next[slug];
    cache = next;
    persist(cache);
    emit();
  }
}

/**
 * Subscribe a component to the generated-roadmap store. Use the result as a
 * dependency so a roadmap saved mid-session (generate button, cross-device
 * fetch) re-renders pages that resolved `undefined` on first paint.
 */
export function useGeneratedRoadmaps(): GeneratedMap {
  return useSyncExternalStore(subscribe, getState, () => EMPTY);
}
