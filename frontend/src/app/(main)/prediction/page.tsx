"use client";

import { Card } from "@/components/ui/Card";

const SAMPLE_DISTRIBUTION = [
  { pathway: "Data Scientist", probability: 0.32 },
  { pathway: "Machine Learning Engineer", probability: 0.24 },
  { pathway: "Software Engineer", probability: 0.18 },
];

export default function PredictionPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Career Path Prediction</h1>
      <p className="text-sm text-slate-500">
        Confidence-ranked distribution from the ensemble (RF + GBT + MLP + LR meta-learner, Phase 5)
        — never a single deterministic outcome.
      </p>
      <Card title="Probability distribution">
        <div className="flex flex-col gap-3">
          {SAMPLE_DISTRIBUTION.map((row) => (
            <div key={row.pathway} className="flex items-center gap-4">
              <span className="w-64 text-sm">{row.pathway}</span>
              <div className="h-4 flex-1 rounded bg-slate-100">
                <div className="h-4 rounded bg-primary" style={{ width: `${row.probability * 100}%` }} />
              </div>
              <span className="font-mono text-sm">{(row.probability * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </Card>
      <Card title="Top contributing features (transparency, Sec. V-D)">
        <p className="text-sm text-slate-500">Feature attributions appear here in Phase 5.</p>
      </Card>
    </div>
  );
}
