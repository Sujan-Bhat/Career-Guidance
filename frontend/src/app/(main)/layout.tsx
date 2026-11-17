"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/api/client";
import AppNav from "@/components/AppNav";

/**
 * Main Layout with Strict Authentication Guard:
 * Prevents unauthenticated users from bypassing the login page by directly
 * navigating to /dashboard, /metrics, /recommendations, etc.
 */
export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState<boolean | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      setAuthorized(false);
      router.replace("/login");
    } else {
      setAuthorized(true);
    }
  }, [router]);

  // While verifying auth token, show a seamless dark loading screen
  if (authorized === null || authorized === false) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#070A14] text-white">
        <div className="flex flex-col items-center gap-4">
          <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-cyan-400 shadow-xl shadow-indigo-500/20 animate-pulse">
            <span className="text-xl font-bold tracking-wider text-white">CM</span>
            <div className="absolute -inset-1 rounded-2xl bg-gradient-to-tr from-violet-600 to-cyan-400 opacity-25 blur-md" />
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-violet-400 animate-ping" />
            <p className="text-xs font-medium tracking-wide text-slate-400">Verifying session...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#0B1020] text-slate-100 lg:flex-row">
      <AppNav />
      <main className="min-w-0 flex-1 bg-[#0B1020] p-4 sm:p-6 lg:p-8">
        {children}
      </main>
    </div>
  );
}
