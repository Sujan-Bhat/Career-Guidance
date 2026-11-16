"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/api/client";

/**
 * Root route gateway:
 * Automatically routes authenticated students directly into the Dashboard,
 * or effortlessly guides new / returning visitors to the Login portal.
 * Seamlessly collapses previously separated tabs into one fluid flow.
 */
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    if (isLoggedIn()) {
      router.replace("/dashboard");
    } else {
      router.replace("/login");
    }
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#070A14] text-white">
      <div className="flex flex-col items-center gap-5">
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-cyan-400 shadow-xl shadow-indigo-500/25 animate-pulse">
          <span className="text-2xl font-black tracking-wider text-white">CM</span>
          <div className="absolute -inset-1 rounded-2xl bg-gradient-to-tr from-violet-600 to-cyan-400 opacity-30 blur-md" />
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
          <p className="text-sm font-medium tracking-wide text-slate-300">Entering CAREERMIND...</p>
        </div>
      </div>
    </div>
  );
}
