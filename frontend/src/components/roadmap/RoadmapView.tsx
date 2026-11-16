"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import type { NodeStatus } from "@/types/roadmap";
import type { Roadmap } from "@/types/roadmap";
import { endpoints, isLoggedIn } from "@/lib/api/client";
import { useProgress } from "@/lib/roadmap/ProgressStore";
import { sanitizeStatuses, statusesFor, summarize } from "@/lib/roadmap/progress";
import { saveGeneratedRoadmap, useGeneratedRoadmaps } from "@/lib/roadmap/generated";
import { careerFromSlug } from "@/lib/roadmap/generate";
import { useDrawerRoute } from "@/lib/roadmap/useDrawerRoute";
import { getRoadmap } from "@/lib/roadmap/registry";
import { AiTutorPill } from "./AiTutorPill";
import { ConfirmDialog } from "./ConfirmDialog";
import { NodeDrawer } from "./NodeDrawer";
import { RoadmapCanvas } from "./RoadmapCanvas";
import { RoadmapErrorBoundary } from "./RoadmapErrorBoundary";
import { RoadmapHeader } from "./RoadmapHeader";
import { RoadmapRequestBox } from "./RoadmapRequestBox";

const SHELL = "mx-auto w-full max-w-[1100px] rounded-2xl bg-slate-50 p-5 sm:p-8";

/**
 * Roadmap page container. The single progress store is the source of truth for
 * both this page and the Dashboard, so the two can never disagree.
 */
export function RoadmapView({ slug }: { slug: string }) {
  // Subscribing re-renders when a roadmap is generated (or restored from the
  // backend) mid-session — `undefined` on first paint then resolves.
  useGeneratedRoadmaps();
  const roadmap = getRoadmap(slug);
  const router = useRouter();
  const { state, ensure, setStatus, reset } = useProgress();
  const [confirming, setConfirming] = useState(false);
  const [shared, setShared] = useState(false);

  const validIds = useMemo(
    () => new Set((roadmap?.nodes ?? []).map((node) => node.id)),
    [roadmap]
  );
  const { nodeId: openId, open, close } = useDrawerRoute(validIds);

  // Opening a roadmap adds it to "My Roadmaps" on the Dashboard.
  useEffect(() => {
    if (roadmap) ensure(roadmap.slug);
  }, [roadmap, ensure]);

  const rawStatuses = statusesFor(state, slug);
  const statuses = useMemo(
    () => (roadmap ? sanitizeStatuses(roadmap, rawStatuses) : rawStatuses),
    [roadmap, rawStatuses]
  );
  const summary = roadmap ? summarize(roadmap, statuses) : null;

  const openNode = openId
    ? roadmap?.nodes.find((node) => node.id === openId)
    : undefined;

  const handleSetStatus = (nodeId: string, status: NodeStatus | null) => {
    setStatus(slug, nodeId, status);
  };

  const handleBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/recommendations");
  };

  const handleShare = async () => {
    const url = window.location.href;
    try {
      if (typeof navigator.share === "function") {
        await navigator.share({ title: roadmap?.title ?? "Career Roadmap", url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setShared(true);
      window.setTimeout(() => setShared(false), 1600);
    } catch {
      /* user dismissed the share sheet */
    }
  };

  if (!roadmap || !summary) {
    return <ComingSoon slug={slug} />;
  }

  return (
    <RoadmapErrorBoundary>
      <div className={SHELL}>
        <RoadmapHeader
          title={roadmap.title}
          description={roadmap.description}
          summary={summary}
          onBack={handleBack}
          onShare={handleShare}
          onReset={() => setConfirming(true)}
        />

        {shared && (
          <p role="status" className="mb-4 text-sm font-medium text-green-700">
            Link copied to clipboard.
          </p>
        )}

        <RoadmapCanvas
          roadmap={roadmap}
          statuses={statuses}
          onOpen={open}
          onSetStatus={handleSetStatus}
        />
      </div>

      <AiTutorPill />

      {openNode && (
        <NodeDrawer
          node={openNode}
          status={statuses[openNode.id]}
          onSetStatus={handleSetStatus}
          onClose={close}
        />
      )}

      {confirming && (
        <ConfirmDialog
          title="Reset progress?"
          message={`This clears every status you have set on ${roadmap.title}. This cannot be undone.`}
          confirmLabel="Reset"
          onConfirm={() => {
            reset(slug);
            setConfirming(false);
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </RoadmapErrorBoundary>
  );
}

/**
 * Friendly fallback for careers that have no seed roadmap yet: restore a
 * previously generated roadmap from the backend when logged in, and offer
 * on-demand Advanced Career Mind AI generation otherwise (or additionally).
 */
function ComingSoon({ slug }: { slug: string }) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Cross-device restore: if this slug was generated on another device,
  // fetch it — saving it re-renders the parent through the store subscription.
  const { data } = useQuery({
    queryKey: ["roadmaps", "detail", slug],
    queryFn: () => endpoints.roadmaps.detail(slug),
    enabled: mounted && isLoggedIn(),
    retry: false,
  });
  const savedRoadmap = data?.data?.roadmap as Roadmap | undefined;
  useEffect(() => {
    if (savedRoadmap) saveGeneratedRoadmap(savedRoadmap);
  }, [savedRoadmap]);

  return (
    <div className={SHELL}>
      <div className="mx-auto max-w-lg rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <h1 className="text-2xl font-bold text-slate-900">
          No roadmap for <span className="break-words">{careerFromSlug(slug)}</span> yet
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          There is no curated roadmap for this career — but you can generate an
          expert path with AI right now. It will be saved to your Dashboard.
        </p>

        <div className="mt-5 text-left">
          <RoadmapRequestBox initialCareer={careerFromSlug(slug)} />
        </div>

        <button
          type="button"
          onClick={() => router.push("/recommendations")}
          className="mt-5 text-sm font-medium text-slate-500 transition-colors hover:text-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          ← Back to Recommendations
        </button>
      </div>
    </div>
  );
}
