"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type State =
  | { kind: "idle" }
  | { kind: "enriching"; startedAt: number }
  | { kind: "navigating" }
  | { kind: "error"; message: string };

type EnrichResponse = {
  topic_id: string;
  topic_number: string;
  enriched: boolean;
  cached: boolean;
  error: string | null;
  pdf_url: string | null;
  pdf_text_chars: number | null;
  dsip_enriched_at: string | null;
};

/**
 * Wraps the "Use this topic →" CTA on the topics page. On click:
 *   1. POST /sbir/topics/{id}/enrich (Apify Playwright DSIP scrape,
 *      up to ~90s — backend caches for 24h so repeat clicks return fast)
 *   2. Show "Pulling from DSIP…" spinner with elapsed time
 *   3. Navigate to /sbir/submit?topic_id=… regardless of enrichment
 *      outcome — the submitter pre-fill uses enriched fields when
 *      available and falls back to sbirdashboard data when not.
 *
 * The user can always click again on the same row; a cached enrichment
 * returns instantly.
 */
export function SBIRUseTopicButton({
  topicId,
  topicNumber
}: {
  topicId: string;
  topicNumber: string;
}) {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "idle" });

  async function onClick() {
    setState({ kind: "enriching", startedAt: Date.now() });
    let res: Response;
    try {
      res = await fetch(`/sbir/topics/${topicId}/enrich`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
    } catch (err) {
      // Network failure — still navigate so the user can submit with
      // sbirdashboard-only data. Stash the error in sessionStorage so
      // the submit page can show a notice.
      stashNotice(
        `DSIP enrichment network error: ${
          err instanceof Error ? err.message : "unknown"
        }`
      );
      goToSubmit();
      return;
    }
    if (!res.ok) {
      let detail = `enrichment failed (${res.status})`;
      try {
        const j = (await res.json()) as { error?: string; detail?: string };
        if (j.error) detail = j.error;
        else if (j.detail) detail = j.detail;
      } catch {
        /* ignore */
      }
      stashNotice(`DSIP enrichment failed: ${detail}`);
      goToSubmit();
      return;
    }
    const body = (await res.json()) as EnrichResponse;
    if (!body.enriched) {
      stashNotice(
        body.error
          ? `DSIP enrichment did not complete: ${body.error}`
          : "DSIP enrichment did not complete — submitting with sbirdashboard data only."
      );
    } else if (body.cached) {
      stashNotice(
        `Using cached DSIP enrichment from ${body.dsip_enriched_at ?? "earlier"}.`
      );
    } else {
      stashNotice(
        `DSIP enrichment complete${
          body.pdf_text_chars
            ? ` — ${body.pdf_text_chars.toLocaleString()} chars of PDF source`
            : ""
        }.`
      );
    }
    goToSubmit();
  }

  function stashNotice(msg: string) {
    try {
      sessionStorage.setItem(`sbir-enrich-notice:${topicId}`, msg);
    } catch {
      /* ignore — sessionStorage may be disabled */
    }
  }

  function goToSubmit() {
    setState({ kind: "navigating" });
    router.push(`/sbir/submit?topic_id=${topicId}`);
  }

  const elapsed =
    state.kind === "enriching"
      ? Math.round((Date.now() - state.startedAt) / 1000)
      : 0;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={state.kind === "enriching" || state.kind === "navigating"}
      className="rounded-md border border-primary bg-primary/10 px-3 py-1 text-xs font-medium text-primary hover:bg-primary/20 disabled:opacity-60"
      title={`Pull full DSIP detail + PDF for ${topicNumber} then open the submitter`}
    >
      {state.kind === "enriching"
        ? `Pulling DSIP… (${elapsed}s)`
        : state.kind === "navigating"
          ? "Opening submitter…"
          : "Use this topic →"}
    </button>
  );
}
