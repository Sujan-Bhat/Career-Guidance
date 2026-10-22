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
  const status = (error as { response?: { status?: number } } | null)?.response?.status;

  const cardStyle =
    "!border !border-slate-800 !bg-[#111827] !text-slate-100 !shadow-lg !shadow-black/10";

  return (
    <div className="min-h-screen bg-[#0B1020] px-4 py-8 text-slate-100 sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">
            Career insights
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Career Path Prediction
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            Confidence-ranked distribution from the ensemble (RF + GBT + MLP +
            LR meta-learner) — never a single deterministic outcome.
          </p>
        </header>

        {isLoading && (
          <p className="rounded-xl border border-slate-800 bg-[#111827] px-4 py-3 text-sm text-slate-400">
            Loading prediction…
          </p>
        )}

        {status === 503 && (
          <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-200">
            The prediction ensemble has not been trained yet — run{" "}
            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-amber-100">
              make train-ensemble
            </code>
            .
          </p>
        )}

        {error && status !== 503 && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            Prediction unavailable — login and try again.
          </p>
        )}

        {payload && (
          <>
            {payload.cold_start && (
              <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-200">
                <span className="font-semibold">Cold start:</span> You are
                viewing a population-average prediction. Add skill assessments
                and complete tracked sessions to personalise it.
              </p>
            )}

            <Card title="Probability distribution" className={cardStyle}>
              <div className="flex flex-col gap-5">
                {distribution.map((row) => {
                  const percentage = row.probability * 100;

                  return (
                    <div key={row.category} className="flex flex-col gap-2">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-slate-200">
                          {label(row.category)}
                        </span>
                        <span className="font-mono text-sm font-semibold tabular-nums text-violet-300">
                          {percentage.toFixed(1)}%
                        </span>
                      </div>

                      <div
                        className="h-3 overflow-hidden rounded-full bg-slate-800"
                        role="progressbar"
                        aria-label={`${label(row.category)} probability`}
                        aria-valuenow={percentage}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-violet-600 to-violet-400 transition-all duration-500"
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-6 border-t border-slate-800 pt-4 text-xs text-slate-500">
                Model {payload.model_version}{" "}
                <span className="mx-1.5 text-slate-700">·</span>
                Predicted{" "}
                {new Date(payload.predicted_at).toLocaleString()}
              </div>
            </Card>

            <Card
              title="Top contributing features (transparency, Sec. V-D)"
              className={cardStyle}
            >
              {topFeatures.length === 0 ? (
                <p className="text-sm text-slate-400">
                  No contributing feature data available.
                </p>
              ) : (
                <ul className="flex flex-col">
                  {topFeatures.map((f) => (
                    <li
                      key={f.feature}
                      className="flex items-center justify-between gap-4 border-b border-slate-800 py-3 last:border-0"
                    >
                      <span className="text-sm text-slate-300">
                        {label(f.feature)}
                      </span>

                      <span
                        className={`rounded-md px-2.5 py-1 font-mono text-sm font-medium tabular-nums ${
                          f.importance >= 0
                            ? "bg-emerald-500/10 text-emerald-400"
                            : "bg-red-500/10 text-red-400"
                        }`}
                      >
                        {f.importance >= 0 ? "+" : ""}
                        {f.importance.toFixed(3)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              <p className="mt-4 rounded-lg border border-slate-800 bg-[#0B1020] px-3 py-3 text-xs leading-5 text-slate-400">
                <span className="font-medium text-emerald-400">Positive</span>{" "}
                values pushed the ensemble toward this prediction;{" "}
                <span className="font-medium text-red-400">negative</span>{" "}
                values pushed against it.
              </p>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}