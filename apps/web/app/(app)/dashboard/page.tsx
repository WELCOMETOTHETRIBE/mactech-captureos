import Link from "next/link";
import { cookies } from "next/headers";
import { CaptureQueues } from "@/components/capture-queues";
import { KeyboardList } from "@/components/keyboard-list";
import { TenantEligibilityCard } from "@/components/tenant-eligibility-card";
import { TermPopover } from "@/components/term-popover";
import { TodaysMoves } from "@/components/todays-moves";
import {
  apiFetch,
  type AgencyEventOut,
  type AgencyEventsResponse,
  type BidInvitesResponse,
  type CaptureQueues as CaptureQueuesData,
  type DashboardResponse,
  type ForecastOut,
  type ForecastsResponse,
  type MeResponse,
  type TenantEligibilityOut
} from "@/lib/api";
import { dueMeta, groupBidInvites, type BidInviteGroup } from "@/lib/bid-invite-view";
import { dismissHowItWorks, showHowItWorks } from "@/lib/preferences";
import {
  EmptyState,
  HpewBadge,
  Kpi,
  LinkButton,
  NoticeTypeBadge,
  PageHeader,
  Pillar,
  ScoreBadge,
  fmtDate,
  fmtMoney,
  fmtRelativeDays
} from "@/components/ui";

export const dynamic = "force-dynamic";

const HOW_IT_WORKS_COOKIE = "mactech.dismiss.howitworks";

export default async function DashboardPage() {
  const [data, me, ck, events, myRecompetes, sdvosbRecompetes, topForecasts, eligibility, bidInvites, captureQueues] = await Promise.all([
    apiFetch<DashboardResponse>("/me/dashboard"),
    apiFetch<MeResponse>("/me"),
    cookies(),
    apiFetch<AgencyEventsResponse>("/events?upcoming_only=true&limit=4").catch(
      () => ({ total: 0, items: [] }) as AgencyEventsResponse
    ),
    apiFetch<ForecastsResponse>(
      "/recompetes?naics_filter=true&mine_only=true&limit=4"
    ).catch(
      () =>
        ({
          total: 0,
          items: [],
          target_naics_filter: false,
          target_naics: []
        }) as ForecastsResponse
    ),
    apiFetch<ForecastsResponse>(
      "/recompetes?naics_filter=true&set_aside_scope=sdvosb&limit=4"
    ).catch(
      () =>
        ({
          total: 0,
          items: [],
          target_naics_filter: false,
          target_naics: []
        }) as ForecastsResponse
    ),
    apiFetch<ForecastsResponse>(
      "/forecasts?naics_filter=true&upcoming_only=true&limit=6"
    ).catch(
      () =>
        ({
          total: 0,
          items: [],
          target_naics_filter: false,
          target_naics: []
        }) as ForecastsResponse
    ),
    apiFetch<TenantEligibilityOut>("/tenant/eligibility").catch(
      () => null as TenantEligibilityOut | null
    ),
    apiFetch<BidInvitesResponse>("/bid-invites?limit=500").catch(
      () =>
        ({
          total: 0,
          counts: { new: 0, reviewed: 0, archived: 0, unseen: 0 },
          items: []
        }) as BidInvitesResponse
    ),
    apiFetch<CaptureQueuesData>("/capture/queues").catch(
      () => null as CaptureQueuesData | null
    )
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
        size="sm"
        eyebrow="This week"
        title={greeting}
        subtitle={
          data.you ? (
            <span className="inline-flex items-center gap-2">
              <Pillar pillar={data.you.pillar} />
              <span className="text-muted-foreground">·</span>
              <span>{data.you.title}</span>
              {data.you.email && (
                <>
                  <span className="text-muted-foreground">·</span>
                  <span className="text-muted-foreground">{data.you.email}</span>
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

      {captureQueues &&
        (captureQueues.pursue_as_prime.length > 0 ||
          captureQueues.team_as_sub.length > 0 ||
          captureQueues.shape_early.length > 0) && (
          <CaptureQueues data={captureQueues} />
        )}

      {onboardingIncomplete && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/40 bg-warning/10 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-warning">
              Setup incomplete
            </p>
            <p className="mt-1 text-sm text-foreground">
              Confirm your{" "}
              <TermPopover kind="tenant_field" value="uei">UEI</TermPopover>,{" "}
              <TermPopover kind="tenant_field" value="cage">CAGE</TermPopover>,
              and set-aside certifications so the proposal drafter can cite
              them. Two minutes.
            </p>
          </div>
          <LinkButton href="/onboarding" variant="warning">
            Finish setup →
          </LinkButton>
        </section>
      )}

      {eligibility && (eligibility.has_hard_blocker || eligibility.blockers.length > 0) && (
        <TenantEligibilityCard eligibility={eligibility} />
      )}

      {firstFeedLoading && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/20 bg-primary/10 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">
              Loading your first feed
            </p>
            <p className="mt-1 text-sm text-foreground">
              {hasNaicsTargets ? (
                <>
                  Pulling opportunities from SAM.gov for your{" "}
                  {(me.tenant.target_naics?.length ?? 0)}{" "}
                  <TermPopover kind="naics" value="overview">NAICS</TermPopover>{" "}
                  targets, then scoring them against your firm profile.
                  Usually 3–10 minutes for the first run; refresh to see
                  opps as they land.
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
          <LinkButton href="/dashboard" variant="primary">
            Refresh ↻
          </LinkButton>
        </section>
      )}

      {/* SPRS chip — eligibility signal for DFARS-7012 / CMMC-L2 work.
          Sourced from Codex (codex.mactechsolutionsllc.com) which owns
          the assessment workflow; we just display + link out. */}
      {(me.tenant.sprs_score !== null || me.tenant.uei) && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3 text-sm">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
              <TermPopover kind="sprs" value="score">
                SPRS
              </TermPopover>{" "}
              ·{" "}
              <TermPopover kind="clause" value="NIST SP 800-171">
                NIST 800-171
              </TermPopover>
            </span>
            {me.tenant.sprs_score !== null ? (
              <>
                <span className="text-2xl font-semibold tabular-nums text-foreground">
                  {me.tenant.sprs_score}
                  <span className="ml-1 text-base font-normal text-muted-foreground">
                    / {me.tenant.sprs_max}
                  </span>
                </span>
                {me.tenant.sprs_assessment_date ? (
                  <span className="text-xs text-muted-foreground">
                    last assessed{" "}
                    {new Date(me.tenant.sprs_assessment_date).toLocaleDateString(
                      undefined,
                      { month: "short", day: "numeric", year: "numeric" }
                    )}
                  </span>
                ) : null}
                {me.tenant.sprs_synced_at ? (
                  <span className="text-[11px] text-muted-foreground">
                    synced from Codex
                  </span>
                ) : (
                  <span className="text-[11px] text-warning">
                    pending Codex sync
                  </span>
                )}
              </>
            ) : (
              <span className="text-sm text-muted-foreground">
                no score on file —{" "}
                <a
                  href="https://codex.mactechsolutionsllc.com/sprs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  start your assessment in Codex →
                </a>
              </span>
            )}
          </div>
          {me.tenant.sprs_score !== null ? (
            <a
              href={
                me.tenant.sprs_source_url ??
                `https://codex.mactechsolutionsllc.com/sprs/${me.tenant.uei ?? ""}`
              }
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-medium text-primary hover:underline"
            >
              View assessment in Codex →
            </a>
          ) : null}
        </section>
      )}

      {/* Action-oriented KPIs — your day at a glance. Three tiles
          (pass 2): the lead tile is "Sweet spots today," demoting
          generic high-fit + deadlines into slots 2/3. Active pursuits +
          Drafts to review move to a one-line "Your work" rail below
          TodaysMoves — they're work-in-flight metrics, not discovery
          questions. Sweet-spots tile is gold-inked only when count > 0;
          zero stays neutral (gravitas, not crying wolf). See brief §7.4. */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link
          href={
            data.you
              ? `/opportunities?sweet_spot_only=true&sort=high_moat_desc&assigned_founder=${data.you.slug}`
              : "/opportunities?sweet_spot_only=true&sort=high_moat_desc"
          }
          className="rounded-lg transition-colors hover:ring-2 hover:ring-primary/30"
        >
          <Kpi
            label="Sweet spots today"
            value={data.kpis.your_sweet_spots_open}
            hint="high-probability easy wins in your lane, not yet in pipeline"
            tone={
              data.kpis.your_sweet_spots_open > 0 ? "high_moat" : "neutral"
            }
          />
        </Link>
        <Link
          href={
            data.you
              ? `/opportunities?assigned_founder=${data.you.slug}&score_min=60`
              : "/opportunities?score_min=60"
          }
          className="rounded-lg transition-colors hover:ring-2 hover:ring-primary/30"
        >
          <Kpi
            label="High-fit, untracked"
            value={data.kpis.your_high_fit_open}
            hint="scored ≥60, not yet in your pipeline"
            tone={data.kpis.your_high_fit_open > 0 ? "brand" : "neutral"}
          />
        </Link>
        <Link
          href="/tools/cyber-scope-parser?filter=high"
          className="rounded-lg transition-colors hover:ring-2 hover:ring-primary/30"
        >
          <Kpi
            label="Cyber scope alerts"
            value={data.kpis.your_cyber_scope_alerts}
            hint="HIGH/CRITICAL, score ≥65, not in pipeline"
            tone={
              data.kpis.your_cyber_scope_alerts > 0 ? "brand" : "neutral"
            }
          />
        </Link>
        <Link
          href="/pipeline"
          className="rounded-lg transition-colors hover:ring-2 hover:ring-primary/30"
        >
          <Kpi
            label="Deadlines this week"
            value={data.kpis.your_deadlines_lt_7d}
            hint="response due in ≤7 days"
            tone={data.kpis.your_deadlines_lt_7d > 0 ? "amber" : "neutral"}
          />
        </Link>
      </section>

      {/* KPI glossary — wraps the bare jargon strings in the tile
          labels with explainer popovers. Sits inline below the strip so
          a layman can hover any term to learn what it means without us
          adding visual noise to the tiles themselves. */}
      <p className="-mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        <span className="uppercase tracking-wider">What these mean:</span>
        <TermPopover kind="score" value="high_fit">
          sweet spot
        </TermPopover>
        <span aria-hidden>·</span>
        <TermPopover kind="score" value="high_fit">
          high-fit
        </TermPopover>
        <span aria-hidden>·</span>
        <TermPopover kind="pursuit_stage" value="overview">
          pipeline
        </TermPopover>
        <span aria-hidden>·</span>
        <TermPopover kind="score" value="overview">
          score
        </TermPopover>
      </p>

      {/* Today's moves — distills the dashboard into 1–3 actions the
          user should take right now. Sits at the top of the action
          flow so the first thing the user sees on opening the app is
          a checklist, not a wall of metrics. */}
      <TodaysMoves
        kpis={data.kpis}
        you={data.you}
        events={events.items}
        recompetes={[
          ...myRecompetes.items,
          ...sdvosbRecompetes.items.filter(
            (r) => !myRecompetes.items.find((m) => m.id === r.id)
          ),
        ]}
      />

      {/* Your work — the work-in-flight pair demoted out of the KPI
          strip per pass-2 brief §7.4. Active pursuits + Drafts to
          review are useful but not discovery-question metrics; a
          single text line keeps them above-fold without competing for
          tile real estate. */}
      <p className="-mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="uppercase tracking-wider">Your work:</span>
        <Link
          href={data.you ? `/pipeline?owner=${data.you.slug}` : "/pipeline"}
          className="text-foreground hover:text-primary hover:underline"
        >
          <span className="font-semibold tabular-nums">
            {data.kpis.your_active_pursuits}
          </span>{" "}
          active pursuits
        </Link>
        <span aria-hidden>·</span>
        <Link
          href="/drafts"
          className="text-foreground hover:text-primary hover:underline"
        >
          <span className="font-semibold tabular-nums">
            {data.kpis.drafts_awaiting_review}
          </span>{" "}
          drafts to review
        </Link>
      </p>

      {!howItWorksDismissed && <HowItWorks />}

      {/* Your top — the thing they came here to see */}
      <section>
        <div className="flex items-baseline justify-between">
          <h2 className="text-base font-semibold text-foreground">
            Your top {data.your_top.length}{" "}
            <span className="font-normal text-muted-foreground">
              — most promising opportunities in your lane
            </span>
          </h2>
          {data.you && (
            <Link
              href={`/opportunities?assigned_founder=${data.you.slug}&score_min=60`}
              className="text-sm font-medium text-primary hover:underline"
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
          <KeyboardList>
          <ul className="mt-4 space-y-3">
            {data.your_top.map((opp, i) => {
              // Sweet-spot row treatment mirrors /opportunities — gold
              // left border + HPEW chip, never as fill. Same token, same
              // shape, same primitive → consistent across surfaces.
              // Hover: switched from `shadow-sm` to `bg-accent/40` per
              // pass-2 brief §7.5 — calmer leaderboard posture.
              const rowClass = opp.is_sweet_spot
                ? "block rounded-lg border border-border border-l-[3px] border-l-[hsl(var(--high-moat))] bg-card p-5 transition-colors hover:bg-accent/40"
                : "block rounded-lg border border-border bg-card p-5 transition-colors hover:bg-accent/40";
              // Promote Claude-generated brief sentence when available.
              const primaryTitle = opp.scope_one_sentence ?? opp.title;
              const hasPromotedTitle = !!opp.scope_one_sentence;
              return (
                <li key={opp.id}>
                  <Link
                    href={opp.detail_url}
                    data-kb-row
                    className={rowClass}
                    title={
                      hasPromotedTitle ? `SAM title: ${opp.title}` : undefined
                    }
                  >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium text-muted-foreground tabular-nums">
                          #{i + 1}
                        </span>
                        <ScoreBadge score={opp.score} size="lg" />
                        {opp.is_sweet_spot && <HpewBadge />}
                        <NoticeTypeBadge type={opp.notice_type} />
                      </div>
                      <h3 className="mt-2 line-clamp-2 text-[15px] font-semibold leading-snug text-foreground">
                        {primaryTitle}
                      </h3>
                      {hasPromotedTitle && (
                        <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                          <span className="uppercase tracking-wider">
                            SAM:
                          </span>{" "}
                          {opp.title}
                        </p>
                      )}
                      <p className="mt-1 text-sm text-muted-foreground">
                        {[opp.agency_short, opp.naics_code && `NAICS ${opp.naics_code}`]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    {/* Deadline gets the right side — the #1 fact for a layman */}
                    <div className="shrink-0 text-right">
                      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                        Deadline
                      </p>
                      <p className="mt-0.5 text-sm font-semibold tabular-nums text-foreground">
                        {fmtRelativeDays(opp.response_deadline, null)}
                      </p>
                    </div>
                  </div>

                  {opp.why_it_matters && (
                    <p className="mt-3 text-sm leading-relaxed text-foreground">
                      {opp.why_it_matters}
                    </p>
                  )}
                  {opp.incumbent_name && (
                    <p className="mt-3 text-sm text-muted-foreground">
                      <span className="font-medium text-foreground">Incumbent:</span>{" "}
                      {opp.incumbent_name}
                      {opp.incumbent_amount != null &&
                        ` — ${fmtMoney(opp.incumbent_amount)} prior obligations`}
                    </p>
                  )}
                  {/* Pass 2 drop: the explicit "Open detail →" line was
                      duplicative — the whole row is already a clickable
                      <Link>. Removed per brief §7.5. */}
                </Link>
              </li>
              );
            })}
          </ul>
          </KeyboardList>
        )}
      </section>

      {/* Coming up rail — three compact columns linking to dedicated
          /forecasts, /events, /recompetes pages. Replaces four separate
          full-width sections that were eating ~250 vertical lines on
          first paint. */}
      <ComingUpRail
        forecasts={topForecasts.items.slice(0, 3)}
        events={events.items.slice(0, 3)}
        recompetes={[
          ...myRecompetes.items.slice(0, 2),
          ...sdvosbRecompetes.items
            .filter(
              (r) => !myRecompetes.items.find((m) => m.id === r.id)
            )
            .slice(0, 1),
        ].slice(0, 3)}
        bidInvites={bidInvites}
      />

      {/* Removed in Sprint C: separate full-width sections for events,
          your recompetes, SDVOSB recompetes, pillar cards, and tenant
          feed. All consolidated into the ComingUpRail above; deep
          views live on the dedicated /events, /recompetes,
          /forecasts, /settings pages reachable from the sidebar. */}
      <footer className="flex flex-wrap items-center justify-between gap-2 pt-2 text-xs text-muted-foreground">
        <span>
          Last refreshed {fmtDate(data.rendered_at)} · Ingestion every 2h ·
          Scoring every 20m · Digest weekdays 6am ET
        </span>
        {howItWorksDismissed && (
          <form action={showHowItWorks}>
            <button
              type="submit"
              className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            >
              Show &ldquo;How CaptureOS works&rdquo;
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
      className="rounded-lg border border-border bg-card p-6"
    >
      <div className="flex items-baseline justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-primary">
          How CaptureOS works
        </p>
        <form action={dismissHowItWorks}>
          <button
            type="submit"
            className="rounded-md px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground"
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
    <li className="rounded-lg border border-border bg-secondary p-4">
      <div className="flex items-baseline gap-2">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground tabular-nums">
          {n}
        </span>
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
      <Link
        href={cta.href}
        className="mt-3 inline-block text-sm font-medium text-primary hover:underline"
      >
        {cta.label}
      </Link>
    </li>
  );
}

/* ── Coming up rail ──────────────────────────────────────────────── */

/** Three-column compact rail replacing the four full-width sections
 *  (Coming to SAM, Where to be, Your recompetes, SDVOSB recompetes)
 *  that used to dominate the dashboard. Each column is a 3-item peek
 *  with a "see all" link to the dedicated page in the sidebar. */
function ComingUpRail({
  forecasts,
  events,
  recompetes,
  bidInvites
}: {
  forecasts: ForecastOut[];
  events: AgencyEventOut[];
  recompetes: ForecastOut[];
  bidInvites: BidInvitesResponse;
}) {
  // Bid invites collapse to project groups so one solicitation with an
  // invite + three reminders reads as a single row. groupBidInvites
  // leads with anything unseen, then falls back to deadline order.
  const inviteGroups = groupBidInvites(
    bidInvites.items.filter((i) => i.status === "new")
  ).slice(0, 3);
  const unseenInvites = bidInvites.counts.unseen;
  return (
    <section className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-4">
      <ComingUpColumn
        label="Bid invites"
        // The count is the headline number, so it tracks what's actually
        // new; the untriaged backlog is the standing state behind it.
        sub={
          unseenInvites > 0
            ? "Arrived since you last looked"
            : "Inbound GC solicitations, due soonest"
        }
        seeAllHref="/bid-invites"
        count={unseenInvites > 0 ? unseenInvites : bidInvites.counts.new}
      >
        {inviteGroups.length === 0 ? (
          <ComingUpEmpty
            msg="No new bid invites."
            ctaLabel="Open the invite inbox"
            ctaHref="/bid-invites"
          />
        ) : (
          inviteGroups.map((g) => (
            <ComingUpBidInviteRow key={g.key} group={g} />
          ))
        )}
      </ComingUpColumn>

      <ComingUpColumn
        label="Coming to SAM"
        sub="Forecasts in your NAICS, 30–180 days out"
        seeAllHref="/forecasts"
        count={forecasts.length}
      >
        {forecasts.length === 0 ? (
          <ComingUpEmpty
            msg="Nothing forecasted yet."
            ctaLabel="Check the full /forecasts feed"
            ctaHref="/forecasts"
          />
        ) : (
          forecasts.map((f) => (
            <ComingUpForecastRow key={f.id} fc={f} />
          ))
        )}
      </ComingUpColumn>

      <ComingUpColumn
        label="Where to be"
        sub="Industry days + pre-solicitation events"
        seeAllHref="/events"
        count={events.length}
      >
        {events.length === 0 ? (
          <ComingUpEmpty
            msg="No upcoming events on the radar."
            ctaLabel="See past events captured"
            ctaHref="/events"
          />
        ) : (
          events.map((ev) => (
            <ComingUpEventRow key={ev.id} ev={ev} />
          ))
        )}
      </ComingUpColumn>

      <ComingUpColumn
        label="Recompetes"
        sub="Forecasts with named incumbents"
        seeAllHref="/recompetes"
        count={recompetes.length}
      >
        {recompetes.length === 0 ? (
          <ComingUpEmpty
            msg="No recompetes flagged in your NAICS."
            ctaLabel="Browse all recompetes"
            ctaHref="/recompetes"
          />
        ) : (
          recompetes.map((f) => (
            <ComingUpForecastRow key={f.id} fc={f} showIncumbent />
          ))
        )}
      </ComingUpColumn>
    </section>
  );
}

function ComingUpColumn({
  label,
  sub,
  seeAllHref,
  count,
  children
}: {
  label: string;
  sub: string;
  seeAllHref: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col rounded-md border border-border bg-card p-4">
      <header className="flex items-baseline justify-between gap-2 border-b border-border pb-2">
        <div>
          <p className="flex items-baseline gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {label}
            {count > 0 && (
              <span className="rounded-sm bg-secondary px-1 text-[10px] tabular-nums text-muted-foreground">
                {count}
              </span>
            )}
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">{sub}</p>
        </div>
        {count > 0 && (
          <Link
            href={seeAllHref}
            className="text-[11px] font-medium text-primary hover:underline"
          >
            See all →
          </Link>
        )}
      </header>
      <ul className="mt-3 flex flex-col divide-y divide-border">
        {children}
      </ul>
    </div>
  );
}

function ComingUpEmpty({
  msg,
  ctaLabel,
  ctaHref,
}: {
  msg: string;
  ctaLabel?: string;
  ctaHref?: string;
}) {
  return (
    <li className="py-4 text-sm">
      <p className="text-muted-foreground">{msg}</p>
      {ctaHref && ctaLabel && (
        <Link
          href={ctaHref}
          className="mt-1 inline-block text-[11px] font-medium text-primary hover:underline"
        >
          {ctaLabel} →
        </Link>
      )}
    </li>
  );
}

function ComingUpBidInviteRow({ group }: { group: BidInviteGroup }) {
  const due = dueMeta(group.bidDueOn);
  return (
    <li className="py-2.5">
      <Link
        href="/bid-invites"
        className="block hover:bg-secondary -mx-2 px-2 py-1 rounded"
      >
        <div className="flex items-baseline justify-between gap-2">
          <p className="line-clamp-1 text-sm font-medium text-foreground">
            {group.unseenCount > 0 && (
              <>
                <span className="sr-only">Unread — </span>
                <span
                  className="mr-1.5 inline-block size-1.5 shrink-0 rounded-full bg-primary align-middle"
                  aria-hidden
                />
              </>
            )}
            {group.projectName}
          </p>
          {due && (
            <span
              className={`shrink-0 text-[10px] font-medium tabular-nums ${
                due.tone === "red"
                  ? "text-destructive"
                  : due.tone === "amber"
                  ? "text-warning"
                  : "text-muted-foreground"
              }`}
            >
              {due.label}
            </span>
          )}
        </div>
        <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
          {group.gcCompany ?? "general contractor"}
          {group.bidPackage ? ` · ${group.bidPackage}` : ""}
        </p>
      </Link>
    </li>
  );
}

function ComingUpForecastRow({
  fc,
  showIncumbent = false
}: {
  fc: ForecastOut;
  showIncumbent?: boolean;
}) {
  // Days until the agency expects to issue the solicitation. The "when
  // does the clock start?" answer is the most useful sub-line a busy
  // BD lead can scan in a 3-row rail.
  const daysToRfp = fc.expected_solicitation_date
    ? Math.ceil(
        (new Date(fc.expected_solicitation_date).getTime() - Date.now()) /
          (1000 * 60 * 60 * 24)
      )
    : null;
  const rfpLabel =
    daysToRfp == null
      ? "RFP date TBD"
      : daysToRfp <= 0
      ? "RFP imminent"
      : daysToRfp <= 30
      ? `RFP in ${daysToRfp}d`
      : `RFP ~${Math.round(daysToRfp / 30)}mo`;
  return (
    <li className="py-2.5">
      <Link
        href={showIncumbent ? "/recompetes" : "/forecasts"}
        className="block hover:bg-secondary -mx-2 px-2 py-1 rounded"
      >
        <div className="flex items-baseline justify-between gap-2">
          <p className="line-clamp-1 text-sm font-medium text-foreground">
            {fc.title}
          </p>
          <span
            className={`shrink-0 text-[10px] font-medium tabular-nums ${
              daysToRfp != null && daysToRfp <= 30
                ? "text-warning"
                : "text-muted-foreground"
            }`}
          >
            {rfpLabel}
          </span>
        </div>
        <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
          {fc.agency ?? "agency"}
          {fc.naics_code ? ` · NAICS ${fc.naics_code}` : ""}
        </p>
        {showIncumbent && fc.incumbent_name && (
          <p className="mt-0.5 line-clamp-1 text-[11px] text-warning">
            Incumbent: {fc.incumbent_name}
          </p>
        )}
      </Link>
    </li>
  );
}

function ComingUpEventRow({ ev }: { ev: AgencyEventOut }) {
  const days = ev.starts_at
    ? Math.ceil(
        (new Date(ev.starts_at).getTime() - Date.now()) /
          (1000 * 60 * 60 * 24)
      )
    : null;
  const dateLabel =
    days == null
      ? "TBD"
      : days < 0
      ? "passed"
      : days === 0
      ? "today"
      : days === 1
      ? "tomorrow"
      : days <= 14
      ? `${days}d`
      : ev.starts_at
      ? new Date(ev.starts_at).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric"
        })
      : "TBD";
  return (
    <li className="py-2.5">
      <a
        href={ev.registration_url ?? ev.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="block hover:bg-secondary -mx-2 px-2 py-1 rounded"
      >
        <div className="flex items-baseline justify-between gap-2">
          <p className="line-clamp-1 text-sm font-medium text-foreground">
            {ev.title}
          </p>
          <span
            className={`shrink-0 text-[10px] font-medium tabular-nums ${
              days != null && days >= 0 && days <= 7
                ? "text-warning"
                : "text-muted-foreground"
            }`}
          >
            {dateLabel}
          </span>
        </div>
        <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
          {ev.agency ?? "agency"}
          {ev.location ? ` · ${ev.location}` : ""}
        </p>
      </a>
    </li>
  );
}
