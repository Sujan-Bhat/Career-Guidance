"use client";

import { useQuery } from "@tanstack/react-query";
import { endpoints } from "@/lib/api/client";
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
  const { data } = useQuery({
    queryKey: ["fes", "submetrics"],
    queryFn: () => endpoints.fes.submetrics(),
  });
  const submetrics: Record<string, number> | null =
    data && !data.data?.detail ? data.data : null;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-3 gap-6">
        <Card title="Focus Efficiency Score" className="flex items-center justify-center">
          <ScoreRing value={null} />
        </Card>
        <Card title="14-Day Trend" className="col-span-2 flex items-center justify-center text-slate-400">
          {/* Phase 8: FES history line chart */}
          Trend chart appears here (Phase 2/3 API + Phase 8 chart)
        </Card>
      </div>
      <Card title="Sub-metric breakdown (paper Sec. V-A)">
        <ul className="grid grid-cols-2 gap-3 text-sm text-slate-700">
          {SUBMETRICS.map((m) => (
            <li key={m.key} className="flex items-center justify-between border-b border-slate-100 py-2">
              <span>{m.label}</span>
              <span className="font-mono">{submetrics ? submetrics[m.key] : "—"}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
