
"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { endpoints } from "@/lib/api/client";
import { useTracking } from "@/lib/tracking/TrackingProvider";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

type Recommendation = {
  recommendation_id: string;
  id: string;
  name: string;
  category: string;
  stage1_eligibility: number;
  stage1_eligible: boolean;
  prerequisites_met: string;
  prerequisites_fraction: number;
  stage2_cf_score: number;
  stage3_fm_score: number;
  contributing_features: Record<string, unknown>;
  decision: "pending" | "accepted" | "rejected";
};

const label = (key: string) =>
  key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

const score = (value: unknown) =>
  typeof value === "number"
    ? value.toFixed(3)
    : value === null || value === undefined
      ? "—"
      : String(value);

export default function RecommendationsPage() {
  const queryClient = useQueryClient();
  const { track } = useTracking();
  const [explanations, setExplanations] = useState<Record<string, string>>({});
  const [explaining, setExplaining] = useState<string | null>(null);
  const [explainError, setExplainError] = useState<Record<string, string>>({});

  const { data, isLoading, error } = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => endpoints.recommendations.list(),
  });

  const decide = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "accept" | "reject" }) => {
      track("recommendation_decision", {
        metadata: { action, recommendation_id: id },
      });
      return action === "accept"
        ? endpoints.recommendations.accept(id)
        : endpoints.recommendations.reject(id);
    },
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["recommendations"] }),
  });

  const explain = async (id: string) => {
    setExplaining(id);
    setExplainError((prev) => ({ ...prev, [id]: "" }));
    try {
      const { data: payload } = await endpoints.recommendations.explain(id);
      setExplanations((prev) => ({ ...prev, [id]: payload.explanation }));
    } catch (err) {
      const response = (
        err as {
          response?: { status?: number; data?: { detail?: string } };
        }
      ).response;
      setExplainError((prev) => ({
        ...prev,
        [id]:
          response?.status === 503
            ? "Explanations need LLM_API_KEY set on the backend."
            : response?.data?.detail || "Explanation unavailable right now.",
      }));
    } finally {
      setExplaining(null);
    }
  };

  const payload = data?.data;
  const recommendations: Recommendation[] = payload?.recommendations ?? [];
  const status = (error as { response?: { status?: number } } | null)?.response?.status;

  const cardStyle =
    "!border !border-slate-800 !bg-[#111827] !text-slate-100 !shadow-lg !shadow-black/10";

  const secondaryButtonStyle =
    "!rounded-lg !border !border-slate-700 !bg-slate-800 !text-slate-200 !transition-colors hover:!border-slate-600 hover:!bg-slate-700";

  return (
    <div className="min-h-screen bg-[#0B1020] px-4 py-8 text-slate-100 sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">
            Career pathways
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Recommendations
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            Three-stage cascade: knowledge-graph filtering → FES-weighted CF →
            FM scoring (paper Sec. V-B). Accept or reject to steer the
            recommender and the RL policy.
          </p>
        </header>

        {isLoading && (
          <p className="rounded-xl border border-slate-800 bg-[#111827] px-4 py-3 text-sm text-slate-400">
            Running the cascade…
          </p>
        )}

        {status === 503 && (
          <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-200">
            The FM model has not been trained yet — run{" "}
            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-amber-100">
              make train-fm
            </code>
            .
          </p>
        )}

        {error && status !== 503 && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            Recommendations unavailable — login and try again.
          </p>
        )}

        {payload && payload.count === 0 && !isLoading && (
          <p className="rounded-xl border border-slate-800 bg-[#111827] px-4 py-4 text-sm text-slate-400">
            No eligible pathways yet — add skill assessments and try again.
          </p>
        )}

        {payload?.cold_start && (
          <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-200">
            <span className="font-semibold">Cold start:</span> rankings lean on
            the population profile. Complete sessions and skill assessments to
            personalise them.
          </p>
        )}

        <div className="flex flex-col gap-4">
          {recommendations.map((rec) => (
            <Card key={rec.recommendation_id} className={cardStyle}>
              <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold text-white">
                      {rec.name}
                    </h2>

                    <span className="rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-xs font-medium text-violet-300">
                      {label(rec.category)}
                    </span>

                    {rec.decision === "accepted" && (
                      <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-300">
                        Accepted
                      </span>
                    )}

                    {rec.decision === "rejected" && (
                      <span className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1 text-xs font-medium text-slate-400">
                        Rejected
                      </span>
                    )}
                  </div>

                  <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-lg border border-slate-800 bg-[#0B1020] p-3">
                      <p className="text-xs text-slate-500">Stage 1 · Knowledge graph</p>
                      <p
                        className={`mt-1 text-sm font-semibold ${
                          rec.stage1_eligible
                            ? "text-emerald-400"
                            : "text-red-400"
                        }`}
                      >
                        {rec.stage1_eligible ? "Eligible" : "Below gate"}
                      </p>
                    </div>

                    <div className="rounded-lg border border-slate-800 bg-[#0B1020] p-3">
                      <p className="text-xs text-slate-500">Prerequisites met</p>
                      <p className="mt-1 text-sm font-semibold text-slate-200">
                        {rec.prerequisites_met}
                        {typeof rec.prerequisites_fraction === "number" &&
                          ` (${(rec.prerequisites_fraction * 100).toFixed(0)}%)`}
                      </p>
                    </div>

                    <div className="rounded-lg border border-slate-800 bg-[#0B1020] p-3">
                      <p className="text-xs text-slate-500">Stage 2 · CF score</p>
                      <p className="mt-1 text-sm font-semibold tabular-nums text-violet-300">
                        {score(rec.stage2_cf_score)}
                      </p>
                    </div>

                    <div className="rounded-lg border border-slate-800 bg-[#0B1020] p-3">
                      <p className="text-xs text-slate-500">Stage 3 · FM score</p>
                      <p className="mt-1 text-sm font-semibold tabular-nums text-teal-300">
                        {score(rec.stage3_fm_score)}
                      </p>
                    </div>
                  </div>

                  {Object.keys(rec.contributing_features ?? {}).length > 0 && (
                    <div className="mt-4">
                      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
                        Contributing features
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(rec.contributing_features ?? {}).map(
                          ([key, value]) => (
                            <span
                              key={key}
                              className="rounded-md border border-slate-800 bg-slate-800/60 px-2.5 py-1.5 text-xs text-slate-300"
                            >
                              <span className="text-slate-400">
                                {label(key)}:
                              </span>{" "}
                              {score(value)}
                            </span>
                          )
                        )}
                      </div>
                    </div>
                  )}

                  {explanations[rec.recommendation_id] && (
                    <div className="mt-4 rounded-xl border border-violet-500/20 bg-violet-500/5 px-4 py-3">
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-violet-300">
                        Why this recommendation?
                      </p>
                      <p className="whitespace-pre-wrap text-sm leading-6 text-slate-300">
                        {explanations[rec.recommendation_id]}
                      </p>
                    </div>
                  )}

                  {explainError[rec.recommendation_id] && (
                    <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
                      {explainError[rec.recommendation_id]}
                    </p>
                  )}
                </div>

                <div className="flex shrink-0 flex-row flex-wrap gap-2 sm:w-36 sm:flex-col">
                  {rec.decision === "pending" ? (
                    <>
                      <Button
                        onClick={() =>
                          decide.mutate({
                            id: rec.recommendation_id,
                            action: "accept",
                          })
                        }
                        className="!rounded-lg !border !border-teal-500 !bg-teal-700 !text-white hover:!bg-teal-600"
                      >
                        Accept
                      </Button>

                      <Button
                        variant="secondary"
                        onClick={() =>
                          decide.mutate({
                            id: rec.recommendation_id,
                            action: "reject",
                          })
                        }
                        className={secondaryButtonStyle}
                      >
                        Reject
                      </Button>
                    </>
                  ) : (
                    <span className="py-2 text-xs text-slate-500">
                      Decision recorded
                    </span>
                  )}

                  <Button
                    variant="secondary"
                    disabled={explaining === rec.recommendation_id}
                    onClick={() => explain(rec.recommendation_id)}
                    className={secondaryButtonStyle}
                  >
                    {explaining === rec.recommendation_id
                      ? "Explaining…"
                      : "Why this?"}
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
