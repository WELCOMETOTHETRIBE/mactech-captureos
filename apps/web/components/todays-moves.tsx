import Link from "next/link";
import type {
  AgencyEventOut,
  DashboardKpis,
  FounderHeader,
  ForecastOut,
} from "@/lib/api";

/**
 * TodaysMoves — distills the dashboard signal into a 3-row checklist
 * of the most actionable next steps. Lives at the very top of the
 * dashboard (above ComingUpRail).
 *
 * The pattern follows Linear/Vercel: a dashboard's job is to answer
 * "what should I do right now?" not "give me every metric." Each row
 * is one concrete action with a one-click destination.
 *
 * Ranking (highest priority wins the top slot):
 *   1. Deadlines closing in ≤7 days  (decide / submit / no-bid)
 *   2. Drafts awaiting review        (review)
 *   3. High-fit untracked            (triage)
 *   4. Industry day in ≤14 days      (RSVP)
 *   5. Recompete you should position for  (research)
 *
 * Renders nothing if no actionable signal is present — empty state
 * is the calm message that there's nothing pressing.
 */

type Move = {
  key: string;
  verb: string;
  label: React.ReactNode;
  href: string;
  tone: "amber" | "brand" | "neutral";
  detail?: string;
};

function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.ceil(ms / (1000 * 60 * 60 * 24));
}

export function TodaysMoves({
  kpis,
  you,
  events,
  recompetes,
}: {
  kpis: DashboardKpis;
  you: FounderHeader | null;
  events: AgencyEventOut[];
  recompetes: ForecastOut[];
}) {
  const moves: Move[] = [];

  if (kpis.your_deadlines_lt_7d > 0) {
    const ownerQ = you ? `?owner=${you.slug}` : "";
    moves.push({
      key: "deadlines",
      verb: "Decide",
      label: (
        <>
          <strong className="text-amber-900">
            {kpis.your_deadlines_lt_7d}
          </strong>{" "}
          {kpis.your_deadlines_lt_7d === 1 ? "pursuit" : "pursuits"} with a
          deadline in ≤7 days
        </>
      ),
      detail: "bid / no-bid on the kanban",
      href: `/pipeline${ownerQ}`,
      tone: "amber",
    });
  }

  if (kpis.drafts_awaiting_review > 0) {
    moves.push({
      key: "drafts",
      verb: "Review",
      label: (
        <>
          <strong>{kpis.drafts_awaiting_review}</strong>{" "}
          {kpis.drafts_awaiting_review === 1 ? "draft" : "drafts"} awaiting
          your sign-off
        </>
      ),
      detail: "Sources Sought + capability statements",
      href: "/drafts",
      tone: "brand",
    });
  }

  if (kpis.your_high_fit_open > 0) {
    const ownerQ = you ? `&assigned_founder=${you.slug}` : "";
    moves.push({
      key: "high-fit",
      verb: "Triage",
      label: (
        <>
          <strong>{kpis.your_high_fit_open}</strong> high-fit{" "}
          {kpis.your_high_fit_open === 1 ? "opp" : "opps"} not yet in your
          pipeline
        </>
      ),
      detail: "scored ≥60, ready to qualify",
      href: `/opportunities?score_min=60${ownerQ}`,
      tone: "brand",
    });
  }

  // Industry day / event in the next 14 days
  const nextEvent = events
    .map((e) => ({ ev: e, days: daysUntil(e.starts_at) }))
    .filter(
      (x): x is { ev: AgencyEventOut; days: number } =>
        x.days !== null && x.days >= 0 && x.days <= 14,
    )
    .sort((a, b) => a.days - b.days)[0];
  if (nextEvent && moves.length < 3) {
    moves.push({
      key: "event",
      verb: "RSVP",
      label: (
        <>
          <strong className="line-clamp-1 inline">
            {nextEvent.ev.title}
          </strong>{" "}
          in {nextEvent.days === 0 ? "today" : `${nextEvent.days}d`}
        </>
      ),
      detail: nextEvent.ev.agency
        ? `${nextEvent.ev.agency}${
            nextEvent.ev.location ? ` · ${nextEvent.ev.location}` : ""
          }`
        : undefined,
      href: nextEvent.ev.registration_url ?? nextEvent.ev.source_url,
      tone: "neutral",
    });
  }

  // Recompete with a named incumbent + a near-term solicitation date
  const nearRecompete = recompetes
    .filter((r) => r.incumbent_name)
    .map((r) => ({ rc: r, days: daysUntil(r.expected_solicitation_date) }))
    .filter(
      (x): x is { rc: ForecastOut; days: number } =>
        x.days !== null && x.days >= 0 && x.days <= 90,
    )
    .sort((a, b) => a.days - b.days)[0];
  if (nearRecompete && moves.length < 3) {
    moves.push({
      key: "recompete",
      verb: "Position",
      label: (
        <>
          recompete vs.{" "}
          <strong className="line-clamp-1 inline">
            {nearRecompete.rc.incumbent_name}
          </strong>{" "}
          — RFP in ~{nearRecompete.days}d
        </>
      ),
      detail: nearRecompete.rc.title,
      href: "/recompetes",
      tone: "neutral",
    });
  }

  // Cap to 3 — anything more is noise on a dashboard.
  const top = moves.slice(0, 3);
  if (top.length === 0) {
    return (
      <section className="rounded-md border border-paper-200 bg-white px-5 py-4">
        <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
          Today&rsquo;s moves
        </p>
        <p className="mt-2 text-sm text-neutral-600">
          Nothing pressing. Good time for a strategic browse —{" "}
          <Link
            href="/opportunities?score_min=60"
            className="font-medium text-brand-700 hover:underline"
          >
            top-scored opps →
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-md border border-paper-200 bg-white">
      <header className="flex items-baseline justify-between border-b border-paper-200 px-5 py-3">
        <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
          Today&rsquo;s moves
        </p>
        <p className="text-[11px] text-neutral-400">
          {top.length === 1 ? "1 thing to do" : `${top.length} things to do`}
        </p>
      </header>
      <ol className="divide-y divide-paper-200">
        {top.map((m, i) => (
          <li key={m.key}>
            <Link
              href={m.href}
              className="group flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-paper-50"
            >
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-neutral-300 bg-white text-[10px] font-semibold text-neutral-600 tabular-nums group-hover:border-brand-500 group-hover:text-brand-700">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span
                    className={`text-[10px] font-semibold uppercase tracking-wider ${
                      m.tone === "amber"
                        ? "text-amber-700"
                        : m.tone === "brand"
                        ? "text-brand-700"
                        : "text-neutral-500"
                    }`}
                  >
                    {m.verb}
                  </span>
                  <span className="min-w-0 truncate text-sm text-neutral-800">
                    {m.label}
                  </span>
                </span>
                {m.detail && (
                  <span className="mt-0.5 block truncate text-[11px] text-neutral-500">
                    {m.detail}
                  </span>
                )}
              </span>
              <span
                aria-hidden
                className="shrink-0 text-neutral-300 group-hover:text-brand-600"
              >
                →
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
