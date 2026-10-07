"use client";

import { useEffect, useState } from "react";

/**
 * Diagnostic link to the FES simulation report — one synthetic student
 * replayed through the same pipeline that scores real sessions, for reading
 * your own sub-metrics against.
 *
 * The report is a GENERATED artifact (`make simulate-fes-html` writes it to
 * `public/`, and it is gitignored), so a fresh checkout genuinely does not
 * have the file. Probing it means the UI links to the report when it exists
 * and otherwise names the command that builds it — never a link that 404s.
 *
 * The browser logs one 404 for the probe while the report is absent; that is
 * the price of not offering a broken link, and it only happens in the state
 * where the page is already telling you how to generate the file.
 */
const REPORT_URL = "/fes-simulation.html";

export function FesReportLink({ className = "" }: { className?: string }) {
  const [ready, setReady] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    fetch(REPORT_URL, { method: "HEAD" })
      .then((response) => active && setReady(response.ok))
      .catch(() => active && setReady(false));
    return () => {
      active = false;
    };
  }, []);

  // Resolved only on the client: rendering nothing until then keeps the
  // server and first client render identical (no hydration mismatch).
  if (ready === null) return null;

  return (
    <p className={className}>
      Diagnostic:{" "}
      {ready ? (
        <>
          <a
            href={REPORT_URL}
            className="font-medium text-slate-500 underline hover:text-primary"
          >
            FES simulation report
          </a>{" "}
          — a synthetic student replayed through this same pipeline, for reading your own
          sub-metrics against.
        </>
      ) : (
        <>
          run <code className="rounded bg-slate-100 px-1">make simulate-fes-html</code> to generate
          the FES simulation report.
        </>
      )}
    </p>
  );
}
