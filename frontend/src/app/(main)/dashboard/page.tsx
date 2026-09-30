"use client";

import { useQuery } from "@tanstack/react-query";
import { endpoints, isLoggedIn } from "@/lib/api/client";
import { Card } from "@/components/ui/Card";
import { ScoreRing } from "@/components/ui/ScoreRing";

const SUBMETRICS = [
  { key: "tcr", label: "Task Completion Rate (TCR)" },
  { key: "sci", label: "Session Consistency Index (SCI)" },
  { key: "dfet", label: "Distraction-Free Engagement (DFET)" },
  { key: "qap", label: "Quiz Attempt Persistence (QAP)" },
  { key: "lrds", label: "Resource Depth Score (LRDS)" },
];

export default function DashboardPage() {
  const loggedIn = typeof window !== "undefined" && isLoggedIn();
  const { data, isLoading, error } = useQuery({
    queryKey: ["fes", "current"],
    queryFn: () => endpoints.fes.current(),
    enabled: loggedIn,
  });
  const { data: historyData } = useQuery({
    queryKey: ["fes", "history"],
    queryFn: () => endpoints.fes.history(),
    enabled: loggedIn,
  });
  const status = (error as { response?: { status?: number } } | null)?.response?.status;

  const fes: number | null = data && !data.data?.detail ? data.data.fes : null;
  const submetrics: Record<string, number> | null =
    data && !data.data?.detail ? data.data : null;

  const history: { date: string; fes: number }[] = historyData?.data?.history ?? [];
  const trend = history.slice(-14);
  const first = trend[0]?.fes;
  const last = trend[trend.length - 1]?.fes;
  const delta = first !== undefined && last !== undefined ? last - first : null;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      {!loggedIn && (
        <p className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Viewing demo data. <a className="font-semibold underline" href="/login">Login</a> to
          track your own sessions and see your personal FES.
        </p>
      )}
      <div className="grid grid-cols-3 gap-6">
        <Card title="Focus Efficiency Score" className="flex items-center justify-center">
          {isLoading ? <span className="text-slate-400">Loading…</span> : <ScoreRing value={fes} />}
        </Card>
        <Card title="14-Day Trend" className="col-span-2">
          {trend.length === 0 ? (
            <div className="flex h-full min-h-[160px] items-center justify-center text-sm text-slate-400">
              No FES history yet — tracked sessions populate this chart.
            </div>
          ) : (
            <div className="flex h-full min-h-[160px] flex-col">
              <div className="mb-2 flex items-baseline gap-2 text-sm text-slate-600">
                <span className="font-semibold text-slate-800">{(last ?? 0).toFixed(3)}</span>
                {delta !== null && (
                  <span className={delta > 0.01 ? "text-green-600" : delta < -0.01 ? "text-red-600" : "text-slate-400"}>
                    {delta > 0.01 ? "▲" : delta < -0.01 ? "▼" : "→"} {Math.abs(delta).toFixed(3)} over{" "}
                    {trend.length} sessions
                  </span>
                )}
              </div>
              <div className="flex flex-1 items-end gap-1">
                {trend.map((point, i) => (
                  <div
                    key={i}
                    className="group relative flex-1 rounded-t bg-primary/80 transition-colors hover:bg-primary"
                    style={{ height: `${Math.max(4, point.fes * 100)}%` }}
                    title={`${String(point.date).slice(0, 10)} — FES ${point.fes.toFixed(3)}`}
                  >
                    <span className="pointer-events-none absolute -top-5 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-white group-hover:block">
                      {point.fes.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-1 flex justify-between text-[10px] text-slate-400">
                <span>{String(trend[0].date).slice(0, 10)}</span>
                <span>{String(trend[trend.length - 1].date).slice(0, 10)}</span>
              </div>
            </div>
          )}
        </Card>
      </div>
      {error && (
        <p className="text-sm text-red-600">
          {status === 401
            ? "Login to see your personal FES and sub-metrics."
            : "FES unavailable — complete a tracked session first (register/login, browse, close the tab)."}
        </p>
      )}
      <Card title="Sub-metric breakdown (paper Sec. V-A)">
        <ul className="grid grid-cols-2 gap-3 text-sm text-slate-700">
          {SUBMETRICS.map((m) => (
            <li key={m.key} className="flex items-center justify-between border-b border-slate-100 py-2">
              <span>{m.label}</span>
              <span className="font-mono">
                {submetrics && submetrics[m.key] !== null && submetrics[m.key] !== undefined
                  ? (submetrics[m.key] as number).toFixed(3)
                  : "—"}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
