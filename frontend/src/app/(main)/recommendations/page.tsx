"use client";

import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

const SAMPLE = [
  { id: "c03", name: "Data Scientist", score: null },
  { id: "c01", name: "Software Engineer", score: null },
  { id: "c05", name: "Machine Learning Engineer", score: null },
];

export default function RecommendationsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Recommendations</h1>
      <p className="text-sm text-slate-500">
        Three-stage cascade: knowledge-graph filtering &rarr; FES-weighted CF &rarr; FM scoring (Phase 4).
      </p>
      <div className="flex flex-col gap-4">
        {SAMPLE.map((rec) => (
          <Card key={rec.id}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold">{rec.name}</h2>
                <p className="text-sm text-slate-500">
                  Explanation citing FES and profile features (NFR07, Phase 7)
                </p>
              </div>
              <div className="flex gap-2">
                <Button onClick={() => {}}>Accept</Button>
                <Button variant="secondary" onClick={() => {}}>
                  Reject
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
