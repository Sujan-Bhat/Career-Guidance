import Link from "next/link";

import type { RoadmapSummary } from "@/lib/roadmap/progress";
import { ProgressBar } from "./ProgressBar";

interface RoadmapCardProps {
  entry: RoadmapSummary;
  onRemove: (slug: string) => void;
}

/**
 * Presentational "My Roadmaps" card for the Dashboard: career name, % complete,
 * done/learning/skipped counts, a progress bar, a Continue link and a remove
 * option.
 */
export function RoadmapCard({ entry, onRemove }: RoadmapCardProps) {
  const { slug, title, description, summary, nextNodeId } = entry;

  const continueHref = nextNodeId
    ? `/roadmap/${slug}?node=${encodeURIComponent(nextNodeId)}`
    : `/roadmap/${slug}`;

  return (
    <div className="group relative flex flex-col justify-between rounded-2xl border border-slate-800 bg-[#0f172a] p-5 shadow-lg shadow-black/20 transition-all duration-200 hover:border-slate-700 hover:shadow-violet-500/5">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-base font-bold text-white transition-colors group-hover:text-violet-300">
              {title}
            </h3>
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-400">
              {description}
            </p>
          </div>

          <button
            type="button"
            onClick={() => onRemove(slug)}
            aria-label={`Remove ${title} from My Roadmaps`}
            title="Delete this roadmap"
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-rose-500/25 bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-400 transition-all hover:border-rose-500/40 hover:bg-rose-500/20 hover:text-rose-300 active:scale-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-rose-500"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-3.5 w-3.5 shrink-0"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
            <span>Delete</span>
          </button>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1">
            <ProgressBar
              percent={summary.percent}
              label={`${title} progress`}
              className="!bg-slate-800 [&>div]:!bg-gradient-to-r [&>div]:!from-violet-500 [&>div]:!to-cyan-400"
            />
          </div>
          <span className="w-10 shrink-0 text-right text-sm font-bold text-cyan-300">
            {summary.percent}%
          </span>
        </div>

        <div className="mt-3.5 flex flex-wrap gap-2 text-xs">
          <span className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 font-medium text-emerald-400">
            {summary.done} done
          </span>
          <span className="rounded-md border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 font-medium text-amber-300">
            {summary.learning} learning
          </span>
          <span className="rounded-md border border-slate-700 bg-slate-800/80 px-2 py-0.5 font-medium text-slate-400">
            {summary.skipped} skipped
          </span>
        </div>
      </div>

      <div className="mt-5 pt-3 border-t border-slate-800/80">
        <Link
          href={continueHref}
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-cyan-500 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-violet-500/20 transition-all hover:from-violet-500 hover:to-cyan-400 active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500"
        >
          <span>Continue</span>
          <span aria-hidden="true">→</span>
        </Link>
      </div>
    </div>
  );
}
