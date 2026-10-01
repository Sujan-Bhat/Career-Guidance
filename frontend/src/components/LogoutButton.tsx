"use client";

import { useRouter } from "next/navigation";
import { clearTokens } from "@/lib/api/client";

/**
 * Clears the JWT pair and navigates to /login. Clearing bumps the auth
 * version, which makes TrackingProvider close the open behavioural session
 * with the token it was opened with before the tokens are gone.
 *
 * `className` lets both nav shells (desktop sidebar bottom slot, mobile
 * drawer row) style the same behaviour consistently.
 */
export default function LogoutButton({ className = "" }: { className?: string }) {
  const router = useRouter();

  return (
    <button
      type="button"
      onClick={() => {
        clearTokens();
        router.push("/login");
      }}
      className={`rounded px-2 py-2 text-left text-sm text-slate-500 hover:bg-primary-light ${className}`}
    >
      Log out
    </button>
  );
}
