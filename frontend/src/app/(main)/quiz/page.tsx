"use client";

import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function QuizPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Skill Self-Assessment</h1>
      <Card title="Sample question">
        <p className="mb-4 text-sm text-slate-700">
          Quiz items feed the QAP sub-metric and skill-assessment scores (Phase 3 backend, Phase 7 LLM generation).
        </p>
        <div className="flex flex-col gap-2">
          {["Option A", "Option B", "Option C", "Option D"].map((opt, i) => (
            <label key={opt} className="flex items-center gap-2 text-sm">
              <input type="radio" name="sample" value={i} /> {opt}
            </label>
          ))}
        </div>
        <Button className="mt-4" onClick={() => {}}>
          Submit attempt
        </Button>
      </Card>
    </div>
  );
}
