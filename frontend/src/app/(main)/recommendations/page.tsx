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
  typeof value === "number" ? value.toFixed(3) : value === null || value === undefined ? "—" : String(value);

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
      track("recommendation_decision", { metadata: { action, recommendation_id: id } });
      return action === "accept"
        ? endpoints.recommendations.accept(id)
        : endpoints.recommendations.reject(id);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["recommendations"] }),
  });

  const explain = async (id: string) => {
    setExplaining(id);
    setExplainError((prev) => ({ ...prev, [id]: "" }));
    try {
      const { data: payload } = await endpoints.recommendations.explain(id);
      setExplanations((prev) => ({ ...prev, [id]: payload.explanation }));
    } catch (err) {
      const response = (err as { response?: { status?: number; data?: { detail?: string } } }).response;
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

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Recommendations</h1>
      <p className="text-sm text-slate-500">
        Three-stage cascade: knowledge-graph filtering &rarr; FES-weighted CF &rarr; FM scoring
        (paper Sec. V-B). Accept or reject to steer the recommender and the RL policy.
      </p>

      {isLoading && <p className="text-sm text-slate-400">Running the cascade…</p>}

      {status === 503 && (
        <p className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          The FM model has not been trained yet — run <code>make train-fm</code>.
        </p>
      )}
      {error && status !== 503 && (
        <p className="text-sm text-red-600">
          Recommendations unavailable — login and try again.
        </p>
      )}

      {payload && payload.count === 0 && !isLoading && (
        <p className="text-sm text-slate-500">
          No eligible pathways yet — add skill assessments and try again.
        </p>
      )}

      {payload?.cold_start && (
        <p className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Cold start: rankings lean on the population profile. Complete sessions and skill
          assessments to personalise them.
        </p>
      )}

      <div className="flex flex-col gap-4">
        {recommendations.map((rec) => (
          <Card key={rec.recommendation_id}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold">{rec.name}</h2>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                    {label(rec.category)}
                  </span>
                  {rec.decision === "accepted" && (
                    <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">Accepted</span>
                  )}
                  {rec.decision === "rejected" && (
                    <span className="rounded bg-slate-200 px-2 py-0.5 text-xs text-slate-600">Rejected</span>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-600">
                  <span>
                    Stage 1 KG:{" "}
                    {rec.stage1_eligible ? (
                      <span className="font-medium text-green-700">eligible</span>
                    ) : (
                      <span className="font-medium text-red-600">below gate</span>
                    )}
                  </span>
                  <span>
                    Prereqs met: {rec.prerequisites_met}
                    {typeof rec.prerequisites_fraction === "number" &&
                      ` (${(rec.prerequisites_fraction * 100).toFixed(0)}%)`}
                  </span>
                  <span>Stage 2 CF: {score(rec.stage2_cf_score)}</span>
                  <span>Stage 3 FM: {score(rec.stage3_fm_score)}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  {Object.entries(rec.contributing_features ?? {}).map(([key, value]) => (
                    <span key={key} className="rounded bg-slate-50 px-2 py-0.5 text-slate-500">
                      {label(key)}: {score(value)}
                    </span>
                  ))}
                </div>
                {explanations[rec.recommendation_id] && (
                  <p className="mt-3 rounded border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-900">
                    {explanations[rec.recommendation_id]}
                  </p>
                )}
                {explainError[rec.recommendation_id] && (
                  <p className="mt-3 text-xs text-amber-700">
                    {explainError[rec.recommendation_id]}
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                {rec.decision === "pending" ? (
                  <div className="flex gap-2">
                    <Button
                      onClick={() =>
                        decide.mutate({ id: rec.recommendation_id, action: "accept" })
                      }
                    >
                      Accept
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        decide.mutate({ id: rec.recommendation_id, action: "reject" })
                      }
                    >
                      Reject
                    </Button>
                  </div>
                ) : (
                  <span className="text-xs text-slate-400">Decision recorded</span>
                )}
                <Button
                  variant="secondary"
                  disabled={explaining === rec.recommendation_id}
                  onClick={() => explain(rec.recommendation_id)}
                >
                  {explaining === rec.recommendation_id ? "Explaining…" : "Why this?"}
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
