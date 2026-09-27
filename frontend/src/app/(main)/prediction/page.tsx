"use client";

import { useQuery } from "@tanstack/react-query";
import { endpoints } from "@/lib/api/client";
import { Card } from "@/components/ui/Card";

type Distribution = { category: string; probability: number };
type FeatureImportance = { feature: string; importance: number };

const label = (key: string) =>
  key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

export default function PredictionPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["careers", "predictions"],
    queryFn: () => endpoints.careers.predictions(),
  });

  const payload = data?.data;
  const distribution: Distribution[] = payload?.distribution ?? [];
  const topFeatures: FeatureImportance[] = payload?.top_features ?? [];
  const status = error?.response?.status;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Career Path Prediction</h1>
      <p className="text-sm text-slate-500">
        Confidence-ranked distribution from the ensemble (RF + GBT + MLP + LR meta-learner)
        — never a single deterministic outcome.
      </p>

      {isLoading && <p className="text-sm text-slate-400">Loading prediction…</p>}

      {status === 503 && (
        <p className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          The prediction ensemble has not been trained yet — run <code>make train-ensemble</code>.
        </p>
      )}
      {error && status !== 503 && (
        <p className="text-sm text-red-600">Prediction unavailable — login and try again.</p>
      )}

      {payload && (
        <>
          {payload.cold_start && (
            <p className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              You are viewing a population-average prediction (cold start). Add skill
              assessments and complete tracked sessions to personalise it.
            </p>
          )}
          <Card title="Probability distribution">
            <div className="flex flex-col gap-3">
              {distribution.map((row) => (
                <div key={row.category} className="flex items-center gap-4">
                  <span className="w-64 text-sm">{label(row.category)}</span>
                  <div className="h-4 flex-1 rounded bg-slate-100">
                    <div
                      className="h-4 rounded bg-primary"
                      style={{ width: `${row.probability * 100}%` }}
                    />
                  </div>
                  <span className="font-mono text-sm">{(row.probability * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-slate-400">
              Model {payload.model_version} · predicted {new Date(payload.predicted_at).toLocaleString()}
            </p>
          </Card>
          <Card title="Top contributing features (transparency, Sec. V-D)">
            <ul className="flex flex-col gap-2 text-sm text-slate-700">
              {topFeatures.map((f) => (
                <li key={f.feature} className="flex items-center justify-between border-b border-slate-100 py-2">
                  <span>{label(f.feature)}</span>
                  <span className={`font-mono ${f.importance >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {f.importance >= 0 ? "+" : ""}
                    {f.importance.toFixed(3)}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-slate-400">
              Positive values pushed the ensemble toward this prediction; negative values pushed against it.
            </p>
          </Card>
        </>
      )}
    </div>
  );
}
