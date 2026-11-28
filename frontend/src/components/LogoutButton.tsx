"use client";

import { useRouter } from "next/navigation";
import { clearTokens } from "@/lib/api/client";

/**
 * Clears the JWT pair and navigates to /login. Clearing bumps the auth
 * version, which makes TrackingProvider close the open behavioural session
 * with the token it was opened with before the tokens are gone.
 */
export default function LogoutButton({ className = "" }: { className?: string }) {
  const router = useRouter();

  return (
    <button
      type="button"
      onClick={() => {
        clearTokens();
        router.push("/login");
        window.sessionStorage.clear();
      }}
      className={`flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-400 transition-colors hover:bg-rose-500/10 hover:text-rose-300 ${className}`}
    >
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
      </svg>
      <span>Sign out</span>
    </button>
  );
}
