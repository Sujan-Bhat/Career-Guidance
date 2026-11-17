import { careerSlug } from "./slug";

/**
 * Shared helpers for the "generate a roadmap with Advanced Career Mind AI" flow — used by both
 * entry points (Dashboard request box, roadmap ComingSoon fallback).
 */

/** Human-readable message for a failed generation request. */
export function describeGenerateError(error: unknown): string {
  const response = (
    error as { response?: { status?: number; data?: { detail?: string } } }
  )?.response;
  const detail = response?.data?.detail;

  switch (response?.status) {
    case 401:
      return "Login to generate and save roadmaps.";
    case 429:
      return "Too many requests — wait a minute and try again.";
    case 503:
      return "AI generation needs LLM_API_KEY set on the backend.";
    case 502:
      return detail || "The model returned an unusable roadmap — try again.";
    default:
      return detail || "Couldn't reach the server — try again.";
  }
}

/**
 * Best-effort display name for a career slug, used to pre-fill the request
 * box on the ComingSoon fallback ("ar-vr-developer" → "Ar Vr Developer").
 * Round-trips: `careerSlug(careerFromSlug(slug)) === slug`.
 */
export function careerFromSlug(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Ensure a name round-trips through the slug (re-exported for tests). */
export function slugRoundTrips(name: string): boolean {
  return careerSlug(careerFromSlug(careerSlug(name))) === careerSlug(name);
}
