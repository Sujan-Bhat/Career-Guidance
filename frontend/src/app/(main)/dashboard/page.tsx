
"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { endpoints, isLoggedIn } from "@/lib/api/client";
import { Card } from "@/components/ui/Card";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { FesReportLink } from "@/components/FesReportLink";

const SUBMETRICS = [
  { key: "tcr", label: "Task Completion Rate (TCR)", activity: "task" },
  { key: "sci", label: "Session Consistency Index (SCI)", activity: "session timing" },
  { key: "dfet", label: "Distraction-Free Engagement (DFET)", activity: "resource" },
  { key: "qap", label: "Quiz Attempt Persistence (QAP)", activity: "quiz" },
  { key: "lrds", label: "Resource Depth Score (LRDS)", activity: "resource" },
];

type SubmetricReading = { value: number; as_of: string } | null;
type SubmetricsPayload = {
  latest?: { computed_at: string; available: string[]; missing: string[] };
  submetrics?: Record<string, SubmetricReading>;
} | null;

const MISSING_ACTIVITY: Record<string, string> = {
  tcr: "task",
  dfet: "resource engagement",
  qap: "quiz",
  lrds: "resource depth",
};

export default function DashboardPage() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const loggedIn = mounted && isLoggedIn();

  const { data, isLoading, error } = useQuery({
    queryKey: ["fes", "current"],
    queryFn: () => endpoints.fes.current(),
    enabled: loggedIn,
    retry: (failureCount, err) => {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status !== 404) return false;
      return failureCount < 3;
    },
    retryDelay: 2000,
  });

  const { data: historyData } = useQuery({
    queryKey: ["fes", "history"],
    queryFn: () => endpoints.fes.history(),
    enabled: loggedIn,
  });

  const { data: subData } = useQuery({
    queryKey: ["fes", "submetrics"],
    queryFn: () => endpoints.fes.submetrics(),
    enabled: loggedIn,
  });

  const status = (error as { response?: { status?: number } } | null)?.response?.status;

  const fes: number | null = data && !data.data?.detail ? data.data.fes : null;
  const breakdown: SubmetricsPayload =
    subData && !subData.data?.detail ? subData.data : null;

  const history: { date: string; fes: number }[] = historyData?.data?.history ?? [];
  const trend = history.slice(-14);
  const first = trend[0]?.fes;
  const last = trend[trend.length - 1]?.fes;
  const delta = first !== undefined && last !== undefined ? last - first : null;

  const missingLocal = (breakdown?.latest?.missing ?? []).filter(
    (k) => k in MISSING_ACTIVITY
  );

  const sparseNote =
    missingLocal.length > 0
      ? `Latest tracked session recorded no ${missingLocal
          .map((k) => MISSING_ACTIVITY[k])
          .join(" / ")} activity — showing each metric's most recent reading.`
      : null;

  const cardStyle =
    "!border !border-slate-800 !bg-[#111827] !text-slate-100 !shadow-lg !shadow-black/10";

  return (
    <div className="min-h-screen bg-[#0B1020] px-4 py-8 text-slate-100 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">
            Overview
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Dashboard
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Track your focus, consistency, and learning engagement.
          </p>
        </header>

        {mounted && !loggedIn && (
          <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-200">
            Viewing demo data.{" "}
            <a
              className="font-semibold text-violet-300 underline hover:text-violet-200"
              href="/login"
            >
              Login
            </a>{" "}
            to track your own sessions and see your personal FES.
          </p>
        )}

        <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
          <Card
            title="Focus Efficiency Score"
            className={`${cardStyle} flex flex-col items-center justify-center`}
          >
            {isLoading ? (
              <span className="py-8 text-sm text-slate-400">Loading…</span>
            ) : (
              <div className="py-2">
                <ScoreRing value={fes} />
              </div>
            )}
            <p className="mt-3 text-center text-xs text-slate-500">
              Your current focus performance
            </p>
          </Card>

          <Card title="14-Day Trend" className={`${cardStyle} md:col-span-2`}>
            {trend.length === 0 ? (
              <div className="flex min-h-[180px] items-center justify-center text-center text-sm text-slate-400">
                No FES history yet — tracked sessions populate this chart.
              </div>
            ) : (
              <div className="flex min-h-[180px] flex-col">
                <div className="mb-5 flex flex-wrap items-baseline gap-3">
                  <span className="text-2xl font-bold tabular-nums text-violet-300">
                    {(last ?? 0).toFixed(3)}
                  </span>

                  {delta !== null && (
                    <span
                      className={`rounded-md px-2 py-1 text-xs font-medium ${
                        delta > 0.01
                          ? "bg-emerald-500/10 text-emerald-400"
                          : delta < -0.01
                            ? "bg-red-500/10 text-red-400"
                            : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      {delta > 0.01 ? "▲" : delta < -0.01 ? "▼" : "→"}{" "}
                      {Math.abs(delta).toFixed(3)} over {trend.length} sessions
                    </span>
                  )}
                </div>

                <div className="flex flex-1 items-end gap-2 border-b border-slate-800 pb-1">
                  {trend.map((point, i) => (
                    <div
                      key={i}
                      className="group relative flex-1 rounded-t-md bg-violet-500/70 transition-colors hover:bg-violet-400"
                      style={{ height: `${Math.max(4, point.fes * 100)}%`, minHeight: "4px" }}
                      title={`${String(point.date).slice(0, 10)} — FES ${point.fes.toFixed(3)}`}
                    >
                      <span className="pointer-events-none absolute -top-6 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] text-white shadow-lg group-hover:block">
                        {point.fes.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="mt-3 flex justify-between text-[10px] text-slate-500">
                  <span>{String(trend[0].date).slice(0, 10)}</span>
                  <span>{String(trend[trend.length - 1].date).slice(0, 10)}</span>
                </div>
              </div>
            )}
          </Card>
        </div>

        {error && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm leading-6 text-red-300">
            {status === 401
              ? "Login to see your personal FES and sub-metrics."
              : "FES unavailable — complete a tracked session first (register/login, browse, close the tab)."}
          </p>
        )}

        <Card title="Sub-metric breakdown (paper Sec. V-A)" className={cardStyle}>
          {sparseNote && (
            <p className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-3 text-xs leading-5 text-amber-200">
              {sparseNote}
            </p>
          )}

          <ul className="grid grid-cols-1 gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
            {SUBMETRICS.map((m) => {
              const reading = breakdown?.submetrics?.[m.key] ?? null;
              const stale =
                reading &&
                breakdown?.latest &&
                new Date(reading.as_of).getTime() !==
                  new Date(breakdown.latest.computed_at).getTime();

              return (
                <li
                  key={m.key}
                  className="flex items-center justify-between gap-3 border-b border-slate-800 py-3"
                >
                  <span className="text-slate-300">{m.label}</span>

                  <span className="shrink-0 text-right font-mono text-slate-200">
                    {reading ? (
                      <>
                        {reading.value.toFixed(3)}
                        {stale && (
                          <span className="mt-1 block font-sans text-[10px] text-slate-500">
                            As of {String(reading.as_of).slice(0, 16).replace("T", " ")}
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </Card>

        <div className="border-t border-slate-800 pt-4">
          <FesReportLink className="text-xs text-violet-300 hover:text-violet-200" />
        </div>
      </div>
    </div>
  );
}
