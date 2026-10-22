
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
  { key: "qap", label: "QAP", name: "Quiz Attempt Persistence", color: "#44351a" },
  { key: "lrds", label: "LRDS", name: "Resource Depth Score", color: "#8b5cf6" },
] as const;

const FES_COLOR = "#a78bfa";
const POPULATION_COLOR = "#64748b";
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
  return present.length
    ? present.reduce((a, b) => a + b, 0) / present.length
    : null;
};

const fmtWhen = (value: string) => String(value).slice(0, 16).replace("T", " ");
const fmtDay = (value: string) => String(value).slice(5, 10);
const num = (value: number | null) => (value === null ? "—" : value.toFixed(3));

const pageStyle = "min-h-screen bg-[#0B1020] px-4 py-8 text-slate-100 sm:px-6";
const cardStyle =
  "!border !border-slate-800 !bg-[#111827] !text-slate-100 !shadow-lg !shadow-black/10";

export default function MetricsPage() {
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
    retry: false,
  });

  if (!mounted) {
    return (
      <div className={pageStyle}>
        <div className="flex flex-col gap-6">
          <h1 className="text-3xl font-bold text-white">Metrics</h1>
          <p className="text-sm text-slate-400">Loading your FES history…</p>
        </div>
      </div>
    );
  }

  if (!loggedIn) {
    return (
      <div className={pageStyle}>
        <div className="flex flex-col gap-6">
          <h1 className="text-3xl font-bold text-white">Metrics</h1>
          <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-200">
            This page charts your own FES sub-metric history from the database,
            so it needs sessions tracked under your account.{" "}
            <a className="font-semibold text-violet-300 underline hover:text-violet-200" href="/login">
              Log in
            </a>{" "}
            to see your metrics.
          </p>
        </div>
      </div>
    );
  }

  const status = (
    historyQuery.error as { response?: { status?: number } } | null
  )?.response?.status;

  const rows: HistoryRow[] = historyQuery.data?.data?.history ?? [];
  const payload: SubmetricsPayload =
    submetricsQuery.data && !submetricsQuery.data.data?.detail
      ? submetricsQuery.data.data
      : null;

  if (historyQuery.isLoading) {
    return (
      <div className={pageStyle}>
        <div className="flex flex-col gap-6">
          <h1 className="text-3xl font-bold text-white">Metrics</h1>
          <p className="text-sm text-slate-400">Loading your FES history…</p>
        </div>
      </div>
    );
  }

  if (status === 401) {
    return (
      <div className={pageStyle}>
        <div className="flex flex-col gap-6">
          <h1 className="text-3xl font-bold text-white">Metrics</h1>
          <p className="text-sm text-slate-400">
            Your session has ended.{" "}
            <a href="/login" className="font-medium text-violet-400 hover:underline">
              Log in
            </a>{" "}
            to view your metrics.
          </p>
        </div>
      </div>
    );
  }

  if (historyQuery.isError) {
    return (
      <div className={pageStyle}>
        <div className="flex flex-col gap-6">
          <h1 className="text-3xl font-bold text-white">Metrics</h1>
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            Could not load your FES history. Try refreshing the page.
          </p>
        </div>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className={pageStyle}>
        <div className="flex flex-col gap-6">
          <h1 className="text-3xl font-bold text-white">Metrics</h1>
          <Card title="No scored sessions yet" className={cardStyle}>
            <p className="text-sm leading-6 text-slate-400">
              FES is computed when a tracked session ends, so browse a few pages
              or open a resource and let the session close — this page fills in
              as sessions are scored. Sub-metrics only appear when the activity
              that produces them was recorded: no quiz means no QAP for that
              session, and the chart leaves a gap rather than plotting a zero.
            </p>
          </Card>
        </div>
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
          (m) =>
            Math.abs(
              (appliedWeights[m.key] ?? 0) -
                (populationWeights[m.key] ?? 0)
            ) < 1e-6
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

  const reversed = [...rows].reverse();

  return (
    <div className={pageStyle}>
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">
              Performance analytics
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-white">
              Metrics
            </h1>
            <p className="mt-2 text-sm text-slate-400">
              FES sub-metric history from the database · {rows.length} scored
              session{rows.length === 1 ? "" : "s"} · {fmtDay(first.date)} →{" "}
              {fmtDay(last.date)}
            </p>
          </div>

          <div className="min-w-48 rounded-xl border border-violet-500/30 bg-violet-500/10 px-5 py-4">
            <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Latest FES
            </p>
            <p className="mt-1 text-3xl font-bold tabular-nums text-violet-300">
              {last.fes.toFixed(3)}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Mean {num(mean(fesValues))} over this window
            </p>
          </div>
        </header>

        <Card title="Sub-metric evolution" className={cardStyle}>
          <MetricChart
            series={series}
            labels={rows.map((row) => fmtDay(row.date))}
            ariaLabel="FES and sub-metric history across scored sessions"
          />

          <ul className="mt-5 flex flex-wrap gap-x-6 gap-y-3 border-t border-slate-800 pt-4 text-xs">
            {METRICS.map((metric) => {
              const values = rows.map((row) => row[metric.key]);
              const present = defined(values);

              return (
                <li key={metric.key} className="flex items-center gap-2">
                  <span
                    className="inline-block h-3 w-3 shrink-0 rounded-sm"
                    style={{ background: metric.color }}
                  />
                  <span className="font-semibold text-slate-200">
                    {metric.label}
                  </span>
                  <span className="text-slate-400">
                    {metric.name} ·{" "}
                    {present.length
                      ? `${Math.min(...present).toFixed(2)}–${Math.max(...present).toFixed(2)} · mean ${mean(values)!.toFixed(2)}`
                      : "never recorded"}
                    {" · "}
                    <span className="text-slate-500">
                      undefined {values.length - present.length}/{values.length}
                    </span>
                  </span>
                </li>
              );
            })}

            <li className="flex items-center gap-2">
              <span
                className="inline-block h-3 w-3 rounded-sm"
                style={{ background: FES_COLOR }}
              />
              <span className="font-semibold text-slate-200">FES</span>
              <span className="text-slate-400">
                Weighted composite · {Math.min(...fesValues).toFixed(2)}–
                {Math.max(...fesValues).toFixed(2)}
              </span>
            </li>
          </ul>

          <FesReportLink className="mt-4 inline-block text-xs text-violet-300 hover:text-violet-200" />
        </Card>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Weights applied (paper Eq. 2)" className={cardStyle}>
            {weightVectors.length ? (
              <>
                <WeightBars vectors={weightVectors} />

                <p className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-400">
                  <span className="flex items-center">
                    <span
                      className="mr-2 inline-block h-3 w-3 rounded-sm"
                      style={{ background: FES_COLOR }}
                    />
                    Applied to your sessions
                  </span>
                  <span className="flex items-center">
                    <span
                      className="mr-2 inline-block h-3 w-3 rounded-sm"
                      style={{ background: POPULATION_COLOR }}
                    />
                    Population cold-start
                  </span>
                </p>

                {stillColdStart && (
                  <p className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-3 text-xs leading-5 text-amber-200">
                    Your scores still use the population weight vector: Eq. 2
                    personal calibration needs 8 sessions, 2 graded outcomes,
                    and at least 3 readings on every sub-metric. Until then your
                    FES is the population&apos;s idea of engagement, not yours.
                  </p>
                )}
              </>
            ) : (
              <p className="text-sm text-slate-400">
                No weight vector recorded yet.
              </p>
            )}
          </Card>

          <Card title="Latest reading per sub-metric" className={cardStyle}>
            <ul className="flex flex-col">
              {METRICS.map((metric) => {
                const reading = payload?.submetrics?.[metric.key] ?? null;
                const stale =
                  reading && payload?.submetrics && last.date
                    ? new Date(reading.as_of).getTime() <
                      new Date(last.date).getTime()
                    : false;

                return (
                  <li
                    key={metric.key}
                    className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 py-3 last:border-0"
                  >
                    <span className="text-sm font-medium text-slate-300">
                      {metric.label}
                      <span className="ml-2 text-xs font-normal text-slate-500">
                        {metric.name}
                      </span>
                    </span>

                    <span className="font-mono text-sm text-slate-200">
                      {reading ? (
                        <>
                          {reading.value.toFixed(3)}
                          {stale && (
                            <span className="ml-2 block text-right font-sans text-[10px] text-amber-400">
                              As of {fmtWhen(reading.as_of)} — not in the latest
                              session
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
        </div>

        <Card title={`Per-session detail (${rows.length})`} className={cardStyle}>
          <div className="max-h-[460px] overflow-auto">
            <table className="w-full min-w-[680px] border-collapse text-sm tabular-nums">
              <thead className="sticky top-0 z-10 bg-[#1E293B]">
                <tr className="text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-3 py-3 text-left">#</th>
                  <th className="px-3 py-3 text-left">Scored at</th>
                  {METRICS.map((metric) => (
                    <th key={metric.key} className="px-3 py-3 text-right">
                      {metric.label}
                    </th>
                  ))}
                  <th className="px-3 py-3 text-right text-violet-300">FES</th>
                </tr>
              </thead>

              <tbody>
                {reversed.map((row, index) => (
                  <tr
                    key={row.session}
                    className="border-b border-slate-800 transition-colors hover:bg-slate-800/50"
                  >
                    <td className="px-3 py-2.5 text-slate-500">
                      {rows.length - index}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-slate-400">
                      {fmtWhen(row.date)}
                    </td>
                    {METRICS.map((metric) => (
                      <td
                        key={metric.key}
                        className={`px-3 py-2.5 text-right ${
                          row[metric.key] === null
                            ? "text-slate-600"
                            : "text-slate-300"
                        }`}
                      >
                        {num(row[metric.key])}
                      </td>
                    ))}
                    <td className="px-3 py-2.5 text-right font-semibold text-violet-300">
                      {row.fes.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}