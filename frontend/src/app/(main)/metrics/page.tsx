"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { endpoints, isLoggedIn } from "@/lib/api/client";
import { Card } from "@/components/ui/Card";
import { MetricChart, type ChartSeries } from "@/components/ui/MetricChart";
import { WeightBars, type WeightVector } from "@/components/ui/WeightBars";
import { FesReportLink } from "@/components/FesReportLink";

/** The five Eq. 1 sub-metrics, in paper order. */
const METRICS = [
  { key: "tcr", label: "TCR", name: "Task Completion Rate", color: "#6366f1" },
  { key: "sci", label: "SCI", name: "Session Consistency Index", color: "#0ea5e9" },
  { key: "dfet", label: "DFET", name: "Distraction-Free Engagement", color: "#10b981" },
  { key: "qap", label: "QAP", name: "Quiz Attempt Persistence", color: "#f59e0b" },
  { key: "lrds", label: "LRDS", name: "Resource Depth Score", color: "#8b5cf6" },
] as const;

const FES_COLOR = "#0f172a";
const POPULATION_COLOR = "#94a3b8";
const HISTORY_LIMIT = 120;

type HistoryRow = {
  session: string;
  date: string;
  fes: number;
  weights: Record<string, number> | null;
  tcr: number | null;
  sci: number | null;
  dfet: number | null;
  qap: number | null;
  lrds: number | null;
};

type SubmetricsPayload = {
  submetrics?: Record<string, { value: number; as_of: string } | null>;
  student_weights?: Record<string, number> | null;
  population_weights?: Record<string, number> | null;
} | null;

const defined = (values: (number | null)[]) =>
  values.filter((v): v is number => v !== null && v !== undefined);

const mean = (values: (number | null)[]) => {
  const present = defined(values);
  return present.length ? present.reduce((a, b) => a + b, 0) / present.length : null;
};

const fmtWhen = (value: string) => String(value).slice(0, 16).replace("T", " ");
const fmtDay = (value: string) => String(value).slice(5, 10);
const num = (value: number | null) => (value === null ? "—" : value.toFixed(3));

export default function MetricsPage() {
  // The JWT lives in localStorage, which the server cannot read: gating on it
  // during render makes the server emit the logged-out tree and the client the
  // logged-in one, which React reports as a hydration error. Gate on `mounted`
  // so the first client render matches the server's.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const loggedIn = mounted && isLoggedIn();

  const historyQuery = useQuery({
    queryKey: ["fes", "history", HISTORY_LIMIT],
    queryFn: () => endpoints.fes.history(HISTORY_LIMIT),
    enabled: loggedIn,
  });
  const submetricsQuery = useQuery({
    queryKey: ["fes", "submetrics"],
    queryFn: () => endpoints.fes.submetrics(),
    enabled: loggedIn,
    retry: false, // a 404 here just means no scored session yet
  });

  if (!mounted) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold">Metrics</h1>
        <p className="text-sm text-slate-500">Loading your FES history…</p>
      </div>
    );
  }

  if (!loggedIn) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold">Metrics</h1>
        <p className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          This page charts your own FES sub-metric history from the database, so it needs sessions
          tracked under your account.{" "}
          <a className="font-semibold underline" href="/login">
            Log in
          </a>{" "}
          to see your metrics.
        </p>
      </div>
    );
  }

  const status = (historyQuery.error as { response?: { status?: number } } | null)?.response?.status;
  const rows: HistoryRow[] = historyQuery.data?.data?.history ?? [];
  const payload: SubmetricsPayload =
    submetricsQuery.data && !submetricsQuery.data.data?.detail ? submetricsQuery.data.data : null;

  if (historyQuery.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold">Metrics</h1>
        <p className="text-sm text-slate-500">Loading your FES history…</p>
      </div>
    );
  }

  if (status === 401) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold">Metrics</h1>
        <p className="text-sm text-slate-600">
          Your session has ended.{" "}
          <a href="/login" className="font-medium text-primary hover:underline">
            Log in
          </a>{" "}
          to view your metrics.
        </p>
      </div>
    );
  }

  if (historyQuery.isError) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold">Metrics</h1>
        <p className="text-sm text-red-600">
          Could not load your FES history. Try refreshing the page.
        </p>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold">Metrics</h1>
        <Card title="No scored sessions yet">
          <p className="text-sm text-slate-600">
            FES is computed when a tracked session ends, so browse a few pages or open a resource
            and let the session close — this page fills in as sessions are scored. Sub-metrics only
            appear when the activity that produces them was recorded: no quiz means no QAP for that
            session, and the chart leaves a gap rather than plotting a zero.
          </p>
        </Card>
      </div>
    );
  }

  const first = rows[0];
  const last = rows[rows.length - 1];
  const fesValues = rows.map((row) => row.fes);
  const appliedWeights = last.weights ?? payload?.student_weights ?? null;
  const populationWeights = payload?.population_weights ?? null;
  const stillColdStart =
    appliedWeights && populationWeights
      ? METRICS.every(
          (m) => Math.abs((appliedWeights[m.key] ?? 0) - (populationWeights[m.key] ?? 0)) < 1e-6,
        )
      : false;

  const series: ChartSeries[] = METRICS.map((metric) => ({
    key: metric.key,
    label: metric.label,
    color: metric.color,
    values: rows.map((row) => row[metric.key]),
  }));
  series.push({
    key: "fes",
    label: "FES",
    color: FES_COLOR,
    strokeWidth: 2.8,
    values: fesValues,
  });

  const weightVectors: WeightVector[] = [
    { label: "applied to your sessions", color: FES_COLOR, weights: appliedWeights },
    { label: "population cold-start", color: POPULATION_COLOR, weights: populationWeights },
  ].filter((vector) => vector.weights !== null);

  const reversed = [...rows].reverse(); // newest session first in the table

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Metrics</h1>
          <p className="text-sm text-slate-500">
            FES sub-metric history from the database · {rows.length} scored session
            {rows.length === 1 ? "" : "s"} · {fmtDay(first.date)} → {fmtDay(last.date)}
          </p>
        </div>
        <div className="rounded-lg border border-primary-light bg-primary-light/50 px-4 py-3 text-right">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Latest FES</p>
          <p className="text-2xl font-bold text-primary">{last.fes.toFixed(3)}</p>
          <p className="text-xs text-slate-500">
            mean {num(mean(fesValues))} over this window
          </p>
        </div>
      </header>

      <Card title="Sub-metric evolution">
        <MetricChart
          series={series}
          labels={rows.map((row) => fmtDay(row.date))}
          ariaLabel="FES and sub-metric history across scored sessions"
        />
        <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs">
          {METRICS.map((metric) => {
            const values = rows.map((row) => row[metric.key]);
            const present = defined(values);
            return (
              <li key={metric.key} className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 rounded-sm"
                  style={{ background: metric.color }}
                />
                <span className="font-semibold text-slate-700">{metric.label}</span>
                <span className="text-slate-500">
                  {metric.name} ·{" "}
                  {present.length
                    ? `${Math.min(...present).toFixed(2)}–${Math.max(...present).toFixed(2)} · mean ${mean(values)!.toFixed(2)}`
                    : "never recorded"}
                  {" · "}
                  <span className="text-slate-400">
                    undefined {values.length - present.length}/{values.length}
                  </span>
                </span>
              </li>
            );
          })}
          <li className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ background: FES_COLOR }} />
            <span className="font-semibold text-slate-700">FES</span>
            <span className="text-slate-500">
              weighted composite · {Math.min(...fesValues).toFixed(2)}–{Math.max(...fesValues).toFixed(2)}
            </span>
          </li>
        </ul>
        <FesReportLink className="mt-4 text-xs text-slate-400" />
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Weights applied (paper Eq. 2)">
          {weightVectors.length ? (
            <>
              <WeightBars vectors={weightVectors} />
              <p className="mt-3 text-xs text-slate-500">
                <span className="mr-3">
                  <span
                    className="mr-1 inline-block h-3 w-3 rounded-sm align-middle"
                    style={{ background: FES_COLOR }}
                  />
                  applied to your sessions
                </span>
                <span>
                  <span
                    className="mr-1 inline-block h-3 w-3 rounded-sm align-middle"
                    style={{ background: POPULATION_COLOR }}
                  />
                  population cold-start
                </span>
              </p>
              {stillColdStart && (
                <p className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  Your scores still use the population weight vector: Eq. 2 personal calibration
                  needs 8 sessions, 2 graded outcomes, and at least 3 readings on every sub-metric.
                  Until then your FES is the population&apos;s idea of engagement, not yours.
                </p>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-400">No weight vector recorded yet.</p>
          )}
        </Card>

        <Card title="Latest reading per sub-metric">
          <ul className="flex flex-col gap-1 text-sm text-slate-700">
            {METRICS.map((metric) => {
              const reading = payload?.submetrics?.[metric.key] ?? null;
              const stale =
                reading && payload?.submetrics && last.date
                  ? new Date(reading.as_of).getTime() < new Date(last.date).getTime()
                  : false;
              return (
                <li
                  key={metric.key}
                  className="flex items-center justify-between border-b border-slate-100 py-2"
                >
                  <span>{metric.label}</span>
                  <span className="font-mono">
                    {reading ? (
                      <>
                        {reading.value.toFixed(3)}
                        {stale && (
                          <span className="ml-1 font-sans text-[10px] text-slate-400">
                            as of {fmtWhen(reading.as_of)} — not in the latest session
                          </span>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>

      <Card title={`Per-session detail (${rows.length})`}>
        <div className="max-h-[460px] overflow-auto">
          <table className="w-full border-collapse text-sm tabular-nums">
            <thead className="sticky top-0 bg-white">
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="px-2 py-2 text-left">#</th>
                <th className="px-2 py-2 text-left">scored at</th>
                {METRICS.map((metric) => (
                  <th key={metric.key} className="px-2 py-2 text-right">
                    {metric.label}
                  </th>
                ))}
                <th className="px-2 py-2 text-right">FES</th>
              </tr>
            </thead>
            <tbody>
              {reversed.map((row, index) => (
                <tr key={row.session} className="border-b border-slate-100">
                  <td className="px-2 py-1.5 text-slate-400">{rows.length - index}</td>
                  <td className="px-2 py-1.5 text-slate-600">{fmtWhen(row.date)}</td>
                  {METRICS.map((metric) => (
                    <td
                      key={metric.key}
                      className={`px-2 py-1.5 text-right ${
                        row[metric.key] === null ? "text-slate-300" : "text-slate-800"
                      }`}
                    >
                      {num(row[metric.key])}
                    </td>
                  ))}
                  <td className="px-2 py-1.5 text-right font-semibold text-slate-900">
                    {row.fes.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
