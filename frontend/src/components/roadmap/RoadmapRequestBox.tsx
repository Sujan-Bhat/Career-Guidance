"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";

import { endpoints } from "@/lib/api/client";
import { useProgress } from "@/lib/roadmap/ProgressStore";
import { saveGeneratedRoadmap } from "@/lib/roadmap/generated";
import { describeGenerateError } from "@/lib/roadmap/generate";
import type { Roadmap } from "@/types/roadmap";

interface RoadmapRequestBoxProps {
  /** Career name to pre-fill the input with (e.g. from the URL slug). */
  initialCareer?: string;
  autoFocus?: boolean;
  /** Compact variant for the dashboard when cards already exist. */
  compact?: boolean;
}

const GENERATION_STAGES = [
  "Contacting Advanced Career Mind AI engine...",
  "Deconstructing career milestones & prerequisites...",
  "Synthesizing structured topics & skill tree nodes...",
  "Curating high-yield learning resources & courses...",
  "Finalizing interactive roadmap layout...",
];

/**
 * "Request a roadmap" — asks the backend to generate one with Advanced Career Mind AI, saves
 * it into the generated-roadmap store, tracks it on the Dashboard, and navigates to it.
 */
export function RoadmapRequestBox({
  initialCareer = "",
  autoFocus = false,
  compact = false,
}: RoadmapRequestBoxProps) {
  const router = useRouter();
  const { ensure } = useProgress();
  const [career, setCareer] = useState(initialCareer);
  const [stageIndex, setStageIndex] = useState(0);

  const generate = useMutation({
    mutationFn: (name: string) => endpoints.roadmaps.generate(name),
    onSuccess: (response) => {
      const roadmap = response.data.roadmap as Roadmap;
      saveGeneratedRoadmap(roadmap);
      ensure(roadmap.slug);
      router.push(`/roadmap/${roadmap.slug}`);
    },
  });

  // Cycle through visual stage messages while waiting for AI generation
  useEffect(() => {
    if (!generate.isPending) {
      setStageIndex(0);
      return;
    }
    const interval = setInterval(() => {
      setStageIndex((prev) => (prev + 1) % GENERATION_STAGES.length);
    }, 3500);
    return () => clearInterval(interval);
  }, [generate.isPending]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const name = career.trim();
    if (!name || generate.isPending) return;
    generate.mutate(name);
  };

  const inputClasses =
    "w-full rounded-xl border border-slate-700 bg-slate-900/90 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 shadow-inner shadow-black/20 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 disabled:opacity-60 transition-all";

  return (
    <div className="space-y-3">
      <form
        onSubmit={submit}
        className={
          compact
            ? "flex flex-col gap-2 sm:flex-row"
            : "flex flex-col gap-3 sm:flex-row"
        }
      >
        <label className="sr-only" htmlFor="roadmap-request-career">
          Career name
        </label>
        <input
          id="roadmap-request-career"
          type="text"
          value={career}
          onChange={(event) => setCareer(event.target.value)}
          placeholder="e.g. AI Research Scientist, DevOps Engineer, Full Stack Developer"
          autoFocus={autoFocus}
          disabled={generate.isPending}
          maxLength={120}
          className={inputClasses}
        />

        <button
          type="submit"
          aria-label="Generate with AI"
          disabled={generate.isPending || career.trim().length === 0}
          className="relative shrink-0 overflow-hidden rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-cyan-500 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-500/20 transition-all hover:from-violet-500 hover:to-cyan-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-400"
        >
          {generate.isPending ? (
            <span className="flex items-center gap-2">
              <svg className="h-4 w-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>Generating…</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5">
              <span>✦</span>
              <span>Generate with AI</span>
            </span>
          )}
        </button>
      </form>

      {/* High-End Visual Generation Loader & Status Box */}
      {generate.isPending && (
        <div
          role="status"
          className="relative overflow-hidden rounded-2xl border border-violet-500/30 bg-gradient-to-r from-violet-950/40 via-indigo-950/30 to-slate-900/60 p-4 shadow-xl backdrop-blur-md animate-in fade-in duration-300"
        >
          {/* Animated top shimmer bar */}
          <div className="absolute top-0 inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-cyan-400 to-transparent animate-pulse" />

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              {/* Animated Glowing Dual Rings Spinner */}
              <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-600/20 border border-violet-500/40">
                <div className="absolute inset-0 rounded-xl border-2 border-violet-400/40 border-t-transparent animate-spin" />
                <span className="text-sm text-cyan-300 animate-pulse">✦</span>
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
                  <p className="text-xs font-bold tracking-wide uppercase text-violet-300">
                    Generating Roadmap with Advanced Career Mind AI
                  </p>
                </div>
                <p className="mt-0.5 text-xs text-slate-300 transition-all duration-300 font-medium">
                  {GENERATION_STAGES[stageIndex]}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-end sm:self-center">
              <span className="rounded-full border border-violet-400/30 bg-violet-500/10 px-2.5 py-1 text-[11px] font-semibold text-violet-200">
                ~15–30s
              </span>
            </div>
          </div>

          {/* Oscillating Progress Track */}
          <div className="mt-3.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-800/80">
            <div className="h-full w-2/5 rounded-full bg-gradient-to-r from-violet-500 via-indigo-400 to-cyan-400 animate-[bounce_2s_infinite]" />
          </div>
        </div>
      )}

      {generate.isError && (
        <p
          role="alert"
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs leading-5 text-amber-200"
        >
          {describeGenerateError(generate.error)}
        </p>
      )}
    </div>
  );
}
