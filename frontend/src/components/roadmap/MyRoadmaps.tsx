"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { endpoints, isLoggedIn } from "@/lib/api/client";
import { useProgress } from "@/lib/roadmap/ProgressStore";
import { mergeGeneratedRoadmaps, useGeneratedRoadmaps } from "@/lib/roadmap/generated";
import { selectTrackedRoadmaps } from "@/lib/roadmap/progress";
import { getRoadmap } from "@/lib/roadmap/registry";
import { activeStudentScope } from "@/lib/roadmap/scope";
import type { Roadmap } from "@/types/roadmap";
import { RoadmapCard } from "./RoadmapCard";
import { RoadmapRequestBox } from "./RoadmapRequestBox";

/**
 * Dashboard "My Roadmaps" section. Reads the same progress store as the
 * roadmap page, so the two can never disagree. Cards are ordered by most
 * recently updated.
 *
 * When logged in, the student's AI-generated roadmaps are fetched from the
 * backend and merged into the generated store, so roadmaps requested on
 * another device resolve here too.
 */
export function MyRoadmaps() {
  const { state, remove, ensure } = useProgress();
  // Subscribing re-renders when a generated roadmap is saved (request box,
  // cross-device restore) so cards resolve without a page reload.
  useGeneratedRoadmaps();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const loggedIn = mounted && isLoggedIn();

  const { data } = useQuery({
    // Scoped by student so cached results never cross accounts.
    queryKey: ["roadmaps", "mine", activeStudentScope()],
    queryFn: () => endpoints.roadmaps.mine(),
    enabled: loggedIn,
    // The list is a convenience (cross-device restore) — never block or
    // spam-retry on failure; local roadmaps still render without it.
    retry: false,
  });

  useEffect(() => {
    const roadmaps = data?.data?.roadmaps;
    if (Array.isArray(roadmaps) && roadmaps.length > 0) {
      const fetched = roadmaps.map((entry) => entry.roadmap as Roadmap);
      mergeGeneratedRoadmaps(fetched);
      // Ensure each fetched roadmap appears in "My Roadmaps" (progress store)
      // so cross-device restores show cards immediately without a page reload.
      for (const rm of fetched) {
        ensure(rm.slug);
      }
    }
  }, [data]);

  // Recomputed on every render; the subscriptions above (
  // `useProgress` state, `generated`) are what trigger re-renders.
  const tracked = selectTrackedRoadmaps(state, getRoadmap);

  if (tracked.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
          No roadmaps yet. Open a career from{" "}
          <span className="font-semibold text-slate-700">Recommendations</span>{" "}
          — or request one here:
        </div>
        <RoadmapRequestBox autoFocus />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        {tracked.map((entry) => (
          <RoadmapCard key={entry.slug} entry={entry} onRemove={remove} />
        ))}
      </div>

      <div className="border-t border-slate-200 pt-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
          Request another roadmap
        </p>
        <RoadmapRequestBox compact />
      </div>
    </div>
  );
}
