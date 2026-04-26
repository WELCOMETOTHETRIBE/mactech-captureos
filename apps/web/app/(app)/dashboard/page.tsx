import Link from "next/link";
import { cookies } from "next/headers";
import { apiFetch, type DashboardResponse, type MeResponse } from "@/lib/api";
import { dismissHowItWorks, showHowItWorks } from "@/lib/preferences";
import {
  Badge,
  EmptyState,
  Kpi,
  LinkButton,
  NoticeTypeBadge,
  PageHeader,
  Pillar,
  ScoreBadge,
  SetAsideBadge,
  fmtDate,
  fmtMoney,
  fmtRelativeDays
} from "@/components/ui";

export const dynamic = "force-dynamic";

const HOW_IT_WORKS_COOKIE = "mactech.dismiss.howitworks";

export default async function DashboardPage() {
  const [data, me, ck] = await Promise.all([
    apiFetch<DashboardResponse>("/me/dashboard"),
    apiFetch<MeResponse>("/me"),
    cookies()
  ]);

  const howItWorksDismissed = ck.get(HOW_IT_WORKS_COOKIE)?.value === "1";
  const onboardingIncomplete =
    me.tenant.onboarding_completed_at === null;

  // First-feed preview banner: onboarding just completed AND no scored
  // opps yet. Two paths:
  //   - target_naics set → SAM ingest + score chain (Sprint 16):
  //     ingest pulls all opps for picked NAICS (~1-3 min per NAICS),
  //     then chains scoring. Worst-case ~10 minutes for 5+ NAICS.
  //   - target_naics empty → score-only against existing corpus
  //     (Sprint 15): ~1-3 minutes.
  // 60-min window covers worst-case for the SAM path.
  const completedAt = me.tenant.onboarding_completed_at
    ? new Date(me.tenant.onboarding_completed_at)
    : null;
  const minsSinceCompletion = completedAt
    ? (Date.now() - completedAt.getTime()) / 60_000
    : Infinity;
  const hasNaicsTargets = (me.tenant.target_naics?.length ?? 0) > 0;
  const firstFeedLoading =
    !onboardingIncomplete &&
    minsSinceCompletion < (hasNaicsTargets ? 60 : 30) &&
    data.kpis.scored_above_60 === 0 &&
    data.kpis.your_high_fit_open === 0 &&
    data.kpis.your_active_pursuits === 0;

  const greeting = data.you
    ? `Good morning, ${data.you.full_name.split(" ")[0]}.`
    : "Dashboard";

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="This week"
        title={greeting}
        subtitle={
          data.you ? (
            <span className="inline-flex items-center gap-2">
              <Pillar pillar={data.you.pillar} />
              <span className="text-neutral-400">·</span>
              <span>{data.you.title}</span>
              {data.you.email && (
                <>
                  <span className="text-neutral-400">·</span>
                  <span className="text-neutral-500">{data.you.email}</span>
                </>
              )}
            </span>
          ) : undefined
        }
        trailing={
          <LinkButton href="/opportunities" variant="secondary">
            Browse all opps →
          </LinkButton>
        }
      />

      {onboardingIncomplete && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">
              Setup incomplete
            </p>
            <p className="mt-1 text-sm text-amber-900">
              Confirm your UEI, CAGE, and set-aside certifications so the
              proposal drafter can cite them. Two minutes.
            </p>
          </div>
          <Link
            href="/onboarding"
            className="rounded-md border border-amber-700 bg-amber-700 px-4 py-2 text-sm font-medium text-white hover:bg-amber-800"
          >
            Finish setup →
          </Link>
        </section>
      )}

      {firstFeedLoading && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-brand-200 bg-brand-50 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">
              Loading your first feed
            </p>
            <p className="mt-1 text-sm text-brand-900">
              {hasNaicsTargets ? (
                <>
                  Pulling opportunities from SAM.gov for your{" "}
                  {(me.tenant.target_naics?.length ?? 0)} NAICS targets, then scoring
                  them against your firm profile. Usually 3–10 minutes for
                  the first run; refresh to see opps as they land.
                </>
              ) : (
                <>
                  Scoring opportunities against your firm profile — usually
                  1–3 minutes. Refresh this page to see the first scored
                  opps as they land.
                </>
              )}
            </p>
          </div>
          <Link
            href="/dashboard"
            className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
          >
            Refresh ↻
          </Link>
        </section>
      )}

      {/* Action-oriented KPIs — your day at a glance */}
      <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Link
          href={
            data.you
              ? `/opportunities?assigned_founder=${data.you.slug}&score_min=60`
              : "/opportunities?score_min=60"
          }
          className="rounded-lg transition-colors hover:ring-2 hover:ring-brand-200"
        >
          <Kpi
            label="High-fit, untracked"
            value={data.kpis.your_high_fit_open}
            hint="scored ≥60, not yet in your pipeline"
            tone={data.kpis.your_high_fit_open > 0 ? "brand" : "neutral"}
          />
        </Link>
        <Link
          href="/pipeline"
          className="rounded-lg transition-colors hover:ring-2 hover:ring-brand-200"
        >
          <Kpi
            label="Deadlines this week"
            value={data.kpis.your_deadlines_lt_7d}
            hint="response due in ≤7 days"
            tone={data.kpis.your_deadlines_lt_7d > 0 ? "amber" : "neutral"}
          />
        </Link>
        <Link
          href={
            data.you ? `/pipeline?owner=${data.you.slug}` : "/pipeline"
          }
          className="rounded-lg transition-colors hover:ring-2 hover:ring-brand-200"
        >
          <Kpi
            label="Active pursuits"
            value={data.kpis.your_active_pursuits}
            hint="in your kanban (excl. won/lost)"
          />
        </Link>
        <Link
          href="/drafts"
          className="rounded-lg transition-colors hover:ring-2 hover:ring-brand-200"
        >
          <Kpi
            label="Drafts to review"
            value={data.kpis.drafts_awaiting_review}
            hint="proposal drafts pending sign-off"
            tone={data.kpis.drafts_awaiting_review > 0 ? "brand" : "neutral"}
          />
        </Link>
      </section>

      {!howItWorksDismissed && <HowItWorks />}

      {/* Your top — the thing they came here to see */}
      <section>
        <div className="flex items-baseline justify-between">
          <h2 className="text-base font-semibold text-neutral-900">
            Your top {data.your_top.length}{" "}
            <span className="font-normal text-neutral-500">
              — most promising opportunities in your lane
            </span>
          </h2>
          {data.you && (
            <Link
              href={`/opportunities?assigned_founder=${data.you.slug}&score_min=60`}
              className="text-sm font-medium text-brand-700 hover:underline"
            >
              See all your assigned →
            </Link>
          )}
        </div>
        {data.your_top.length === 0 ? (
          <div className="mt-3">
            <EmptyState
              title="No high-fit opportunities in your lane today."
              body={
                data.you
                  ? `Nothing currently scored \u2265 60 with your NAICS / set-aside profile and assigned to ${data.you.full_name.split(" ")[0]}. Ingestion runs every 2h, scoring every 20m \u2014 the next sweep may add some.`
                  : "Once your account is linked to a founder profile, your top scored opportunities will surface here."
              }
              action={
                <div className="flex justify-center gap-2">
                  <LinkButton href="/opportunities?score_min=40" variant="primary">
                    Browse opps ≥ 40
                  </LinkButton>
                  <LinkButton href="/opportunities" variant="secondary">
                    Browse all
                  </LinkButton>
                </div>
              }
            />
          </div>
        ) : (
          <ul className="mt-4 space-y-3">
            {data.your_top.map((opp, i) => (
              <li key={opp.id}>
                <Link
                  href={opp.detail_url}
                  className="block rounded-lg border border-neutral-200 bg-white p-5 transition-colors hover:border-brand-300 hover:shadow-sm"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-neutral-400 tabular-nums">
                          #{i + 1}
                        </span>
                        <ScoreBadge score={opp.score} size="lg" />
                        <NoticeTypeBadge type={opp.notice_type} />
                      </div>
                      <h3 className="mt-2 text-base font-semibold leading-snug text-neutral-900">
                        {opp.title}
                      </h3>
                      <p className="mt-1 text-sm text-neutral-500">
                        {[opp.agency_short, opp.naics_code && `NAICS ${opp.naics_code}`]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    {/* Deadline gets the right side — the #1 fact for a layman */}
                    <div className="shrink-0 text-right">
                      <p className="text-[11px] uppercase tracking-wide text-neutral-500">
                        Deadline
                      </p>
                      <p className="mt-0.5 text-sm font-semibold tabular-nums text-neutral-800">
                        {fmtRelativeDays(opp.response_deadline, null)}
                      </p>
                    </div>
                  </div>

                  {opp.why_it_matters && (
                    <p className="mt-3 text-sm leading-relaxed text-neutral-700">
                      {opp.why_it_matters}
                    </p>
                  )}
                  {opp.incumbent_name && (
                    <p className="mt-3 text-sm text-neutral-600">
                      <span className="font-medium text-neutral-800">Incumbent:</span>{" "}
                      {opp.incumbent_name}
                      {opp.incumbent_amount != null &&
                        ` — ${fmtMoney(opp.incumbent_amount)} prior obligations`}
                    </p>
                  )}
                  <p className="mt-3 text-sm font-medium text-brand-700">
                    Open detail →
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Pillar cards */}
      <section>
        <h2 className="text-base font-semibold text-neutral-900">
          Pillars{" "}
          <span className="font-normal text-neutral-500">
            — your team's coverage
          </span>
        </h2>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          {data.pillar_cards.map((p) => (
            <Link
              key={p.slug}
              href={`/opportunities?assigned_founder=${p.slug}&score_min=60`}
              className="block rounded-lg border border-neutral-200 bg-white p-5 transition-colors hover:border-brand-300 hover:shadow-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <Pillar pillar={p.pillar} />
                <Badge tone="neutral">@{p.slug}</Badge>
              </div>
              <p className="mt-3 text-sm font-medium text-neutral-900">
                {p.full_name}
              </p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-neutral-900">
                {p.high_score_count}
              </p>
              <p className="text-xs text-neutral-500">scored ≥ 60</p>
            </Link>
          ))}
        </div>
      </section>

      {/* Tenant vital signs — context, smaller */}
      <section className="rounded-lg border border-dashed border-neutral-200 bg-neutral-50 p-4">
        <p className="text-xs uppercase tracking-wide text-neutral-500">
          Tenant feed
        </p>
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-neutral-700">
          <span>
            <strong className="tabular-nums text-neutral-900">
              {data.kpis.opportunities_total.toLocaleString()}
            </strong>{" "}
            opportunities ingested
          </span>
          <span>
            <strong className="tabular-nums text-neutral-900">
              {data.kpis.opportunities_last_24h.toLocaleString()}
            </strong>{" "}
            new in last 24h
          </span>
          <span>
            <strong className="tabular-nums text-neutral-900">
              {data.kpis.scored_above_60.toLocaleString()}
            </strong>{" "}
            scored ≥ 60
          </span>
          <span>
            <strong className="tabular-nums text-neutral-900">
              {data.kpis.enriched_with_incumbent.toLocaleString()}
            </strong>{" "}
            with incumbent intel
          </span>
        </div>
      </section>

      <footer className="flex flex-wrap items-center justify-between gap-2 pt-2 text-xs text-neutral-500">
        <span>
          Last refreshed {fmtDate(data.rendered_at)} · Ingestion every 2h ·
          Scoring every 20m · Digest weekdays 6am ET
        </span>
        {howItWorksDismissed && (
          <form action={showHowItWorks}>
            <button
              type="submit"
              className="rounded-md px-2 py-1 text-xs text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800"
            >
              Show "How CaptureOS works"
            </button>
          </form>
        )}
      </footer>
    </div>
  );
}

function HowItWorks() {
  return (
    <section
      aria-label="How CaptureOS works"
      className="rounded-lg border border-neutral-200 bg-white p-6"
    >
      <div className="flex items-baseline justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-brand-700">
          How CaptureOS works
        </p>
        <form action={dismissHowItWorks}>
          <button
            type="submit"
            className="rounded-md px-2 py-0.5 text-xs text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800"
            aria-label="Dismiss this guide"
            title="Hide this guide. You can always show it again from the footer."
          >
            Dismiss ✕
          </button>
        </form>
      </div>
      <ol className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <Step
          n={1}
          title="Browse"
          body="Every federal SAM.gov notice gets a 0–100 score against your NAICS, set-aside, and capability statements. Higher = better fit."
          cta={{ href: "/opportunities", label: "Open the feed →" }}
        />
        <Step
          n={2}
          title="Triage"
          body="Open an opportunity, read the why-it-matters and capability matches. Click \u201CAdd to pipeline\u201D to track it."
          cta={{ href: "/opportunities?score_min=60", label: "Top scored →" }}
        />
        <Step
          n={3}
          title="Track"
          body="Pursuits flow Lead \u2192 Submit \u2192 Won/Lost on the kanban. The drafter generates Sources Sought responses on demand."
          cta={{ href: "/pipeline", label: "Open kanban →" }}
        />
      </ol>
    </section>
  );
}

function Step({
  n,
  title,
  body,
  cta
}: {
  n: number;
  title: string;
  body: string;
  cta: { href: string; label: string };
}) {
  return (
    <li className="rounded-lg border border-neutral-100 bg-neutral-50 p-4">
      <div className="flex items-baseline gap-2">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white tabular-nums">
          {n}
        </span>
        <h3 className="text-sm font-semibold text-neutral-900">{title}</h3>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-neutral-600">{body}</p>
      <Link
        href={cta.href}
        className="mt-3 inline-block text-sm font-medium text-brand-700 hover:underline"
      >
        {cta.label}
      </Link>
    </li>
  );
}
