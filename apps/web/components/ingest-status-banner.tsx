import type { IngestStatus } from "@/lib/api";

/**
 * Feed health for the opportunity board.
 *
 * Reports the last *successful* ingest, never the last attempt. A run that
 * fails auth still stamps last_run_at, so a banner built on last_run_at
 * would have read "updated 2 hours ago" through the entire 19-day SAM.gov
 * key outage in June 2026 — the failure mode this component exists to make
 * impossible.
 */

function relativeAge(iso: string | null): string {
  if (!iso) return "never";
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function isAuthError(err: string | null): boolean {
  return !!err && /API_KEY_INVALID|401|403|unauthor/i.test(err);
}

export function IngestStatusBanner({ status }: { status: IngestStatus | null }) {
  // Advisory surface: if the health probe itself failed, say nothing rather
  // than claim a state we don't know.
  if (!status || status.status === "unknown") return null;

  const age = relativeAge(status.last_success_at);

  if (status.status === "ok") {
    return (
      <p className="text-[11px] text-slate-500">
        Feed current — last opportunities added {age}.
      </p>
    );
  }

  const failing = status.status === "failing";
  const tone = failing
    ? "border-red-300 bg-red-50 text-red-900"
    : "border-amber-300 bg-amber-50 text-amber-900";

  let headline: string;
  if (failing) {
    headline = `No new opportunities since ${age} — every source is failing.`;
  } else if (status.status === "stale") {
    headline = `No new opportunities since ${age}.`;
  } else {
    headline = `${status.sources_error} of ${
      status.sources_error + status.sources_ok
    } sources are failing — last successful update ${age}.`;
  }

  return (
    <div className={`rounded-md border p-3 ${tone}`}>
      <p className="flex items-center gap-2 text-sm font-medium">
        <span aria-hidden>!</span> {headline}
      </p>
      {isAuthError(status.first_error) ? (
        <p className="mt-1 text-[12px]">
          SAM.gov is rejecting the API key. Keys expire and must be regenerated
          at sam.gov under Account Details → API Key, then updated in the
          workers service as SAM_API_KEY. The board below is a snapshot from
          before the outage.
        </p>
      ) : status.first_error ? (
        <p className="mt-1 font-mono text-[11px] opacity-80">
          {status.first_error}
        </p>
      ) : null}
    </div>
  );
}
