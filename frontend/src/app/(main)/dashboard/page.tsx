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
  });

  const fes: number | null = data && !data.data?.detail ? data.data.fes : null;
  const submetrics: Record<string, number> | null =
    data && !data.data?.detail ? data.data : null;

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
        <Card title="14-Day Trend" className="col-span-2 flex items-center justify-center text-slate-400">
          Trend chart appears here (Phase 8)
        </Card>
      </div>
      {error && (
        <p className="text-sm text-red-600">
          FES unavailable — complete a tracked session first (register/login, browse, close the tab).
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
