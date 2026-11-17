/**
 * Returns a stable scope identifier for the currently authenticated student,
 * or "anon" when not logged in.
 *
 * Used as a TanStack Query cache key segment so queries are invalidated / isolated
 * per-student across account switches.
 */
export function activeStudentScope(): string {
  if (typeof window === "undefined") return "anon";
  const token = window.localStorage.getItem("cm_access_token");
  if (!token) return "anon";
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return "anon";
    // atob is standard in browser and modern Node.js environments
    const payload = JSON.parse(
      typeof atob === "function"
        ? atob(parts[1])
        : Buffer.from(parts[1], "base64").toString("utf-8")
    );
    return payload.sub ?? "anon";
  } catch {
    return "anon";
  }
}
