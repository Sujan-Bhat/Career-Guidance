"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { endpoints } from "@/lib/api/client";
import { Card } from "@/components/ui/Card";

type ProblemRow = {
  slug: string;
  question_id: string;
  title: string;
  difficulty: "Easy" | "Medium" | "Hard";
  topic_tags: string[];
  solved: boolean;
};

const DIFF_COLOR: Record<string, string> = {
  Easy: "text-emerald-400",
  Medium: "text-amber-400",
  Hard: "text-rose-400",
};

export default function PracticePage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["problems", page, search, difficulty],
    queryFn: () => endpoints.problems.list({ page, search, difficulty }),
  });

  const problems: ProblemRow[] = data?.data?.problems ?? [];
  const total: number = data?.data?.total ?? 0;

  return (
    <div className="min-h-screen bg-[#0B1020] px-4 py-8 text-slate-100 sm:px-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <header>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">
            Coding Practice
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Problems ({total})
          </h1>
        </header>

        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search problems..."
            className="min-w-0 flex-1 rounded-lg border border-slate-800 bg-[#111827] px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-violet-500 focus:outline-none"
          />
          <select
            value={difficulty}
            onChange={(e) => {
              setDifficulty(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-800 bg-[#111827] px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none"
          >
            <option value="">All Difficulties</option>
            <option value="Easy">Easy</option>
            <option value="Medium">Medium</option>
            <option value="Hard">Hard</option>
          </select>
        </div>

        <Card className="!border !border-slate-800 !bg-[#111827]">
          {isLoading ? (
            <p className="py-8 text-center text-sm text-slate-400">Loading problems…</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-800 text-xs uppercase text-slate-400">
                  <tr>
                    <th className="py-3 pr-4">Status</th>
                    <th className="py-3 pr-4">Title</th>
                    <th className="py-3 pr-4">Difficulty</th>
                    <th className="py-3">Topics</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {problems.map((p) => (
                    <tr key={p.slug} className="hover:bg-slate-800/40">
                      <td className="py-3 pr-4">{p.solved ? "✅" : "—"}</td>
                      <td className="py-3 pr-4 font-medium text-white">
                       <a href={`https://leetcode.com/problems/${p.slug}/`} target="_blank" rel="noopener noreferrer" className="hover:text-violet-400">
                       {p.question_id}. {p.title} ↗
                       </a>
                      </td>
                      <td className={`py-3 pr-4 font-semibold ${DIFF_COLOR[p.difficulty] ?? ""}`}>
                        {p.difficulty}
                      </td>
                      <td className="py-3 text-xs text-slate-400">
                        {p.topic_tags.slice(0, 3).join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-4 text-xs text-slate-400">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-lg border border-slate-700 px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              type="button"
              disabled={page * 50 >= total}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-lg border border-slate-700 px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}