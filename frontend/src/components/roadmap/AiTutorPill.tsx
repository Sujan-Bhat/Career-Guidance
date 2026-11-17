"use client";

import { AI_TUTOR_ENABLED } from "@/lib/roadmap/flags";

/**
 * Floating bottom-centre "AI Tutor" pill. Renders nothing unless the
 * `NEXT_PUBLIC_AI_TUTOR` feature flag is enabled; the input is a stub.
 */
export function AiTutorPill() {
  if (!AI_TUTOR_ENABLED) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-5 z-40 flex justify-center px-4">
      <form
        onSubmit={(event) => event.preventDefault()}
        className="pointer-events-auto flex w-full max-w-md items-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-2.5 shadow-lg"
      >
        <label htmlFor="ai-tutor-input" className="sr-only">
          Ask the AI Tutor a question
        </label>
        <input
          id="ai-tutor-input"
          type="text"
          placeholder="AI Tutor – Have a question? Type here"
          className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 placeholder:text-slate-500 focus:outline-none"
        />
        <button
          type="submit"
          aria-label="Send question"
          className="rounded-full bg-[#2B78E4] px-3 py-1 text-xs font-semibold text-white transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
