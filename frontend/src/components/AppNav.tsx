
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import LogoutButton from "@/components/LogoutButton";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/metrics", label: "Metrics" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/prediction", label: "Career Prediction" },
  { href: "/quiz", label: "Quizzes" },
  { href: "/chat", label: "Guidance Chat" },
  { href: "/profile", label: "Profile" },
];

const linkClasses = (active: boolean) =>
  [
    "block rounded-lg px-3 py-2.5 text-sm transition-colors",
    active
      ? "border border-violet-400/20 bg-violet-400/10 font-medium text-violet-300"
      : "text-slate-300 hover:bg-slate-800 hover:text-white",
  ].join(" ");

export default function AppNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Close the mobile drawer when the route changes.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Close the mobile drawer when Escape is pressed.
  useEffect(() => {
    if (!open) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };

    window.addEventListener("keydown", onKey);

    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(`${href}/`);

  return (
    <>
      {/* Desktop sidebar */}
      <nav className="hidden w-60 shrink-0 flex-col gap-1 border-r border-slate-800 bg-[#0B1020] p-4 lg:sticky lg:top-0 lg:flex lg:h-screen">
        <Link
          href="/"
          className="mb-6 rounded-lg px-2 py-3 text-lg font-bold tracking-wide text-white"
        >
          CAREERMIND
        </Link>

        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={linkClasses(isActive(item.href))}
          >
            {item.label}
          </Link>
        ))}

        <LogoutButton className="mt-auto" />
      </nav>

      {/* Mobile header */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-800 bg-[#0B1020] px-4 py-3 lg:hidden">
        <Link
          href="/"
          className="text-base font-bold tracking-wide text-white"
        >
          CAREERMIND
        </Link>

        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="rounded-lg p-2 text-slate-300 transition-colors hover:bg-slate-800 hover:text-white"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            aria-hidden="true"
          >
            {open ? (
              <path
                d="M5 5l10 10M15 5L5 15"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            ) : (
              <path
                d="M3 5h14M3 10h14M3 15h14"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            )}
          </svg>
        </button>
      </header>

      {/* Mobile drawer and backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 lg:hidden"
          role="dialog"
          aria-modal="true"
        >
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setOpen(false)}
            className="absolute inset-0 h-full w-full cursor-default bg-slate-900/40"
          />

          <nav className="absolute inset-y-0 right-0 flex w-64 flex-col gap-1 border-l border-slate-800 bg-[#0B1020] p-4 shadow-2xl shadow-black/40">
            <div className="mb-3 flex items-center justify-between px-1">
              <span className="text-base font-bold tracking-wide text-white">
                CAREERMIND
              </span>

              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="rounded-lg p-2 text-slate-300 transition-colors hover:bg-slate-800 hover:text-white"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 20 20"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M5 5l10 10M15 5L5 15"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>

            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={linkClasses(isActive(item.href))}
              >
                {item.label}
              </Link>
            ))}

            <LogoutButton className="mt-auto border-t border-slate-800 pt-3" />
          </nav>
        </div>
      )}
    </>
  );
}
