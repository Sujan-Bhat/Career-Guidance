"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import LogoutButton from "@/components/LogoutButton";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/prediction", label: "Career Prediction" },
  { href: "/quiz", label: "Quizzes" },
  { href: "/chat", label: "Guidance Chat" },
  { href: "/profile", label: "Profile" },
];

const linkClasses = (active: boolean) =>
  [
    "block rounded px-3 py-2 text-sm transition-colors",
    active
      ? "bg-primary-light font-medium text-primary-dark"
      : "text-slate-700 hover:bg-primary-light",
  ].join(" ");

/**
 * Responsive navigation: a persistent sidebar from `lg` up, and below it a
 * sticky header with a hamburger toggling a slide-in drawer (closes on
 * navigation, Escape, or backdrop tap).
 */
export default function AppNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Close the drawer whenever the route changes (link taps inside the drawer).
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Escape closes the drawer.
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
      {/* Desktop sidebar (lg+) */}
      <nav className="hidden w-56 flex-col gap-1 border-r border-slate-200 bg-white p-4 lg:flex">
        <Link href="/" className="mb-4 px-2 text-lg font-bold text-primary">
          CAREERMIND
        </Link>
        {NAV.map((item) => (
          <Link key={item.href} href={item.href} className={linkClasses(isActive(item.href))}>
            {item.label}
          </Link>
        ))}
        <LogoutButton className="mt-auto" />
      </nav>

      {/* Mobile header (<lg) */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <Link href="/" className="text-base font-bold text-primary">
          CAREERMIND
        </Link>
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="rounded p-2 text-slate-600 hover:bg-primary-light"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            {open ? (
              <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            ) : (
              <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </header>

      {/* Mobile drawer + backdrop */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setOpen(false)}
            className="absolute inset-0 h-full w-full cursor-default bg-slate-900/40"
          />
          <nav className="absolute inset-y-0 right-0 flex w-64 flex-col gap-1 bg-white p-4 shadow-xl">
            <div className="mb-3 flex items-center justify-between px-1">
              <span className="text-base font-bold text-primary">CAREERMIND</span>
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="rounded p-2 text-slate-600 hover:bg-primary-light"
              >
                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className={linkClasses(isActive(item.href))}>
                {item.label}
              </Link>
            ))}
            <LogoutButton className="mt-auto border-t border-slate-200 pt-3" />
          </nav>
        </div>
      )}
    </>
  );
}
