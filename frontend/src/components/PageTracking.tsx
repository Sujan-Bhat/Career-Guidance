"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { useTracking } from "@/lib/tracking/TrackingProvider";

/**
 * Emits a `page_view` behavioural event on every route change so live
 * sessions always carry at least the interaction stream the FES engine
 * needs (previously the tracking SDK was exported but never called).
 */
export function PageTracking() {
  const pathname = usePathname();
  const { track } = useTracking();
  const last = useRef<string | null>(null);

  useEffect(() => {
    if (!pathname || last.current === pathname) return;
    last.current = pathname;
    track("page_view", { metadata: { path: pathname } });
  }, [pathname, track]);

  return null;
}
