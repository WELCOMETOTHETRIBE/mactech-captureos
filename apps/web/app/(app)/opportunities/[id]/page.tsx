import Link from "next/link";
import { notFound } from "next/navigation";
import {
  apiFetch,
  type BriefOut,
  type CyberSummaryOut,
  type DraftListResponse,
  type MeResponse,
  type OpportunityDetail,
  type PursuitCard as PursuitCardT,
  type PursuitStage,
  type QuestionListResponse,
  type QuestionOut,
  type ScoreBlock,
  type TermExplanationResponse
} from "@/lib/api";
import { createPursuit, deletePursuit, updatePursuit } from "@/lib/pursuits";
import { deleteOpportunityQuestion } from "@/lib/ask";
import { AskStreamingPanel } from "@/components/ask-streaming";
import { AnnotatedProse } from "@/components/annotated-prose";
import { CyberFitCard } from "@/components/cyber-posture-card";
import { CyberScopeStrip } from "@/components/cyber-scope-strip";
import { StreamingDraftButton } from "@/components/draft-streaming";
import { generateOpportunityBrief } from "@/lib/brief";
import {
  BackLink,
  Badge,
  Button,
  Card,
  ExplainLink,
  HpewBadge,
  LinkButton,
  NaicsBadge,
  NoticeTypeBadge,
  PageHeader,
  ScoreBadge,
  SetAsideBadge,
  fmtDate,
  fmtMoney,
  fmtRelativeDays
} from "@/components/ui";
import { STAGE_LABEL, STAGE_TONE } from "@/lib/pursuit-stages";

export const dynamic = "force-dynamic";

const SCORE_COMPONENT_LABELS: Record<string, string> = {
  naics_match: "NAICS match",
  keyword_density: "Keyword density",
  set_aside_fit: "Set-aside fit",
  value_sanity: "Value sanity",
  incumbent_weakness: "Incumbent weakness",
  founder_availability: "Founder availability",
  freshness: "Freshness",
  capability_match: "Capability match"
};

const SCORE_COMPONENT_MAX: Record<string, number> = {
  naics_match: 25,
  keyword_density: 15,
  set_aside_fit: 15,
  value_sanity: 10,
  incumbent_weakness: 10,
  founder_availability: 5,
  freshness: 5,
  capability_match: 15
};

const SCORE_COMPONENT_HELP: Record<string, string> = {
  naics_match:
    "Boosts when the opportunity's NAICS code is one of MacTech's 8 primary codes (full points) or 12 secondary codes (partial).",
  keyword_density:
    "Counts how often domain keywords (cybersecurity, RMF, ATO, infrastructure, etc.) appear in the title and description.",
  set_aside_fit:
    "SDVOSB-set-aside opportunities score highest. Small-business set-asides next, then unrestricted. NaSDQOSB set-asides cap the field.",
  value_sanity:
    "Penalizes opportunities outside MacTech's plausible ceiling range — too small to be worth pursuing, or too big for current bonding capacity.",
  incumbent_weakness:
    "Looks at incumbent obligations + contract end date. Higher when the incumbent is mid-cycle or has fewer prior wins (more vulnerable).",
  founder_availability:
    "Bonus when the assigned-pillar founder isn't already saturated with active pursuits.",
  freshness:
    "Recently posted opportunities score higher than ones approaching their archive date.",
  capability_match:
    "Cosine similarity between the opportunity's embedding and MacTech's capability statements. Higher = closer match to what we already do."
};

export default async function OpportunityDetailPage({
  params,
  searchParams
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ explain?: string; view?: string }>;
}) {
  const [{ id }, sp] = await Promise.all([params, searchParams]);
  const explainSlug = sp.explain?.trim() || null;
  // Brief / Raw tab is a search-param toggle (pass 2). Default: "brief"
  // when present, "raw" when null (gives the user something to read
  // immediately rather than an empty brief panel). Any other value
  // falls through to the default — never throw.
  const viewParam = sp.view === "brief" || sp.view === "raw" ? sp.view : null;

  let data: OpportunityDetail;
  try {
    data = await apiFetch<OpportunityDetail>(`/opportunities/${id}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  // Triage-view fetches: only what a capture lead needs to decide
  // bid/no-bid in 30 seconds. Solicitation matrices, amendments, agency
  // intel, web mentions, and Q&A history live on the pursuit detail
  // page now (post-decision deep work).
  const [
    me,
    pursuit,
    drafts,
    questions,
    brief,
    explanation,
    cyberSummary
  ] = await Promise.all([
    apiFetch<MeResponse>("/me"),
    apiFetch<PursuitCardT>(`/pursuits/by-opportunity/${id}`).catch(
      () => null as PursuitCardT | null
    ),
    apiFetch<DraftListResponse>(`/opportunities/${id}/drafts`).catch(
      () => ({ total: 0, items: [] }) as DraftListResponse
    ),
    apiFetch<QuestionListResponse>(`/opportunities/${id}/questions`).catch(
      () => ({ total: 0, items: [], starters: {} }) as QuestionListResponse
    ),
    apiFetch<BriefOut>(`/opportunities/${id}/brief`).catch(
      () => null as BriefOut | null
    ),
    explainSlug
      ? apiFetch<TermExplanationResponse>(
          `/explain/${encodeURIComponent(explainSlug)}`,
          { timeoutMs: 45_000 }
        ).catch(() => null as TermExplanationResponse | null)
      : Promise.resolve(null as TermExplanationResponse | null),
    apiFetch<CyberSummaryOut>(`/opportunities/${id}/cyber-summary`).catch(
      () => null as CyberSummaryOut | null
    )
  ]);

  const opp = data.opportunity;

  return (
    <div
      className={
        explainSlug
          ? "grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]"
          : ""
      }
    >
      <div className="min-w-0 space-y-6">
      <BackLink href="/opportunities">All opportunities</BackLink>

      {/* Header — uses the standard PageHeader display variant so this
          page's "top" matches every other detail page in the suite. The
          chip row + score + open-on-SAM CTA collapse into the subtitle
          and trailing slots respectively. */}
      <PageHeader
        display
        eyebrow={opp.agency ?? "Agency unknown"}
        title={opp.title}
        subtitle={
          <div className="flex flex-wrap items-center gap-2">
            {opp.notice_type ? (
              <ExplainLink
                slug={`notice_type:${opp.notice_type
                  .toLowerCase()
                  .replace(/\s+/g, "_")
                  .slice(0, 60)}`}
              >
                <NoticeTypeBadge type={opp.notice_type} />
              </ExplainLink>
            ) : (
              <NoticeTypeBadge type={opp.notice_type} />
            )}
            {opp.set_aside ? (
              <ExplainLink slug={`set_aside:${opp.set_aside}`}>
                <SetAsideBadge code={opp.set_aside} />
              </ExplainLink>
            ) : (
              <SetAsideBadge code={opp.set_aside} />
            )}
            {opp.naics_code && (
              <ExplainLink slug={`naics:${opp.naics_code}`}>
                <NaicsBadge code={opp.naics_code} />
              </ExplainLink>
            )}
            {opp.solicitation_number && (
              <Badge tone="neutral">Sol# {opp.solicitation_number}</Badge>
            )}
          </div>
        }
        trailing={
          <div className="flex shrink-0 items-center gap-3">
            {data.score && <ScoreBadge score={data.score.score} />}
            {opp.sam_link && (
              <LinkButton href={opp.sam_link} external variant="primary">
                Open on SAM.gov →
              </LinkButton>
            )}
          </div>
        }
      />

      {/* Meta strip — moved out of the header so PageHeader stays
          focused on title + chips + CTA. */}
      <section className="rounded-md border border-border bg-card p-5">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 text-sm">
          <Meta label="Posted" value={fmtDate(opp.posted_at)} />
          <Meta
            label="Deadline"
            value={fmtRelativeDays(opp.response_deadline, opp.days_until_deadline)}
          />
          <Meta
            label="Set-aside"
            value={
              opp.set_aside_description ?? opp.set_aside ?? (
                <span className="text-muted-foreground">unrestricted</span>
              )
            }
          />
          <Meta
            label="Notice ID"
            value={<span className="break-all font-mono text-xs">{opp.notice_id}</span>}
          />
        </div>
      </section>

      {/* "Why this is high-moat" strip — gated to opps where the
          parallel high-moat scorer returned >= 70 (per pass-2 brief
          §11 Q1). Sits BELOW the meta strip and ABOVE the two-column
          main so first-visit triage sees the decision evidence before
          any do-work affordance. Falls back to render nothing when
          the score is null or below threshold. */}
      <HighMoatStrip score={data.score} />
      <CyberScopeStrip opportunityId={id} score={data.score} />

      {/* Two-column main: description (with brief tab) left, incumbent +
          capability right. Pre-decision evidence — brief + cyber-fit +
          incumbent + capability — sits ABOVE the take-action rail
          (pass-2 brief §7.1). */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BriefAndDescriptionPanel
          opportunityId={opp.id}
          description={data.description}
          brief={brief}
          samResourceLinks={data.sam_resource_links}
          view={viewParam}
        />

        <div className="space-y-4">
          {cyberSummary && <CyberFitCard summary={cyberSummary} />}
          <Card title="Incumbent intelligence">
            {data.incumbent && data.incumbent.name ? (
              <>
                <p className="text-base font-semibold text-foreground">
                  {data.incumbent.name}
                </p>
                <dl className="mt-3 grid grid-cols-1 gap-2 text-sm">
                  {data.incumbent.uei && (
                    <Row label="UEI">
                      <span className="font-mono text-xs">{data.incumbent.uei}</span>
                    </Row>
                  )}
                  {data.incumbent.contract_amount != null && (
                    <Row label="Cumulative obligations">
                      <span className="tabular-nums">
                        {fmtMoney(data.incumbent.contract_amount)}
                      </span>
                    </Row>
                  )}
                  {data.incumbent.contract_end_date && (
                    <Row label="Contract end date">
                      {fmtDate(data.incumbent.contract_end_date)}
                    </Row>
                  )}
                  {data.incumbent.exclusions && (
                    <Row label="Exclusions check">
                      {data.incumbent.exclusions.is_excluded ? (
                        <Badge tone="red">ON DEBARMENT LIST</Badge>
                      ) : (
                        <span className="inline-flex items-center gap-2">
                          <Badge tone="green">clean</Badge>
                          <span className="text-xs text-muted-foreground">
                            {fmtDate(data.incumbent.exclusions.checked_at)}
                          </span>
                        </span>
                      )}
                    </Row>
                  )}
                </dl>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                No incumbent identified yet.{" "}
                {data.enrichment_notes ?? "Enrichment may still be pending."}
              </p>
            )}
          </Card>

          <Card title="MacTech capability matches">
            {data.capability_matches.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No capability statements ranked. Either embeddings haven&rsquo;t populated
                yet or similarity is below threshold.
              </p>
            ) : (
              <ul className="space-y-3">
                {data.capability_matches.slice(0, 4).map((m) => (
                  <li key={m.id} className="border-b border-border pb-3 last:border-b-0 last:pb-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-sm font-semibold text-foreground">{m.title}</p>
                      <Badge tone="blue">sim {m.similarity.toFixed(2)}</Badge>
                    </div>
                    <p className="mt-1 line-clamp-3 text-xs text-muted-foreground">{m.summary}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {/* Take action — post-decision affordances wrapped under a quiet
          section header (pass-2 brief §7.1 + §11 Q5 — all three panels
          stay expanded, no accordion). PursuitPanel + DrafterPanel +
          AskPanel internals unchanged; only their position relative to
          the brief / cyber-fit / incumbent evidence above changes.
          A user landing on a high-moat opp now sees the decision
          evidence first; the do-work surface sits below it. */}
      <section className="space-y-4 border-t border-border pt-6">
        <header>
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Take action on this opportunity
          </p>
        </header>
        <PursuitPanel
          opportunityId={opp.id}
          pursuit={pursuit}
          meFounderSlug={me.founder?.slug ?? null}
        />
        <DrafterPanel
          opportunityId={opp.id}
          drafts={drafts}
          noticeType={opp.notice_type}
        />
        <AskPanel
          opportunityId={opp.id}
          questions={questions}
          meFounderSlug={me.founder?.slug ?? null}
        />
      </section>

      {/* Score + rationale — full-width */}
      {data.score ? (
        <section className="rounded-md border border-border bg-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Score
              </p>
              <div className="mt-1 flex items-baseline gap-2">
                <p className="text-4xl font-semibold tabular-nums text-foreground">
                  {data.score.score}
                </p>
                <p className="text-sm text-muted-foreground">/ 100</p>
              </div>
              {data.score.assigned_founder_slug && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Assigned to{" "}
                  <span className="font-medium text-foreground">
                    @{data.score.assigned_founder_slug}
                  </span>
                </p>
              )}
              {data.score.scored_at && (
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Scored {fmtDate(data.score.scored_at)}
                </p>
              )}
            </div>
            {data.score.why_it_matters && (
              <div className="min-w-0 flex-1 lg:max-w-xl">
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Why this matters
                </p>
                <p className="mt-1 text-sm leading-relaxed text-foreground">
                  <AnnotatedProse text={data.score.why_it_matters} />
                </p>
                {data.score.why_it_matters_model && (
                  <p className="mt-2 text-[10px] text-muted-foreground">
                    via {data.score.why_it_matters_model}
                  </p>
                )}
              </div>
            )}
          </div>

          <details className="mt-5 border-t border-border pt-3 group">
            <summary className="flex cursor-pointer items-baseline justify-between gap-3 list-none">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground group-hover:text-foreground">
                Score breakdown
                <span className="ml-2 text-muted-foreground group-open:hidden">↓ Show</span>
                <span className="ml-2 hidden text-muted-foreground group-open:inline">↑ Hide</span>
              </p>
              <p className="text-[11px] text-muted-foreground">
                Hover any component for the rule.
              </p>
            </summary>
            <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(data.score.breakdown).map(([k, v]) => {
                const max = SCORE_COMPONENT_MAX[k];
                const pct = max ? Math.min(100, Math.max(0, (v / max) * 100)) : 0;
                const help = SCORE_COMPONENT_HELP[k];
                return (
                  <li
                    key={k}
                    title={help}
                    className="rounded-md border border-border bg-secondary px-3 py-2 transition-colors hover:border-primary/40 hover:bg-card"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <ExplainLink
                        slug={`score_component:${k}`}
                        className="-mx-1 px-1"
                      >
                        <span className="text-xs text-foreground">
                          {SCORE_COMPONENT_LABELS[k] ?? k}
                        </span>
                      </ExplainLink>
                      <span className="tabular-nums text-sm font-medium text-foreground">
                        {v}
                        {max && (
                          <span className="text-[10px] text-muted-foreground"> / {max}</span>
                        )}
                      </span>
                    </div>
                    {max && (
                      <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-foreground"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    )}
                    {help && (
                      <p className="mt-1.5 line-clamp-2 text-[10px] leading-snug text-muted-foreground">
                        {help}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </details>
        </section>
      ) : (
        <Card title="Score">
          <p className="text-sm text-muted-foreground">
            Not scored yet. The scoring engine runs every 20 minutes — once embeddings and
            enrichment land, this opportunity will appear with a score breakdown and a
            Claude-written rationale.
          </p>
        </Card>
      )}
      </div>

      {explainSlug && (
        <ExplainRail slug={explainSlug} explanation={explanation} oppId={id} />
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-0.5">{value}</p>
    </div>
  );
}

/**
 * HighMoatStrip — renders the "Why this is high-moat" evidence strip
 * directly under the meta strip on the opportunity detail page. Gated
 * to high-moat scores >= 70 per pass-2 brief §11 Q1. When the gate
 * fails the component renders nothing — the strip is absent rather
 * than present-but-empty.
 *
 * Visual contract per brief §6 + §11 Q3: 3px gold left border, no fill
 * and no background tint. Left half is the Claude-seeded
 * `why_it_matters_seed` (italic-serif to echo the page H1). Right half
 * is a 3-column meta grid of clause / clearance / role evidence.
 */
function HighMoatStrip({ score }: { score: ScoreBlock | null }) {
  if (!score || !score.high_moat) return null;
  const hm = score.high_moat;
  if (hm.score < 70) return null;

  const hasClauses = hm.clause_hits.length > 0;
  const hasClearance = hm.top_clearance && hm.top_clearance !== "NONE";
  const hasRoles = hm.role_hits.length > 0;
  const hasAnyMeta = hasClauses || hasClearance || hasRoles;

  return (
    <section
      className="rounded-md border border-border border-l-[3px] border-l-[hsl(var(--high-moat))] bg-card p-5"
      aria-label="Why this is high-moat"
    >
      <div className="flex flex-wrap items-baseline gap-2">
        <p className="text-[11px] font-medium uppercase tracking-wider text-[hsl(var(--high-moat))]">
          Why this is high-moat
        </p>
        {hm.is_high_probability_easy_win && <HpewBadge size="sm" />}
      </div>

      <div className="mt-3 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="min-w-0">
          {hm.why_it_matters_seed ? (
            <p className="text-[15px] font-medium italic leading-snug font-serif text-foreground">
              <AnnotatedProse text={hm.why_it_matters_seed} />
            </p>
          ) : (
            <p className="text-sm leading-relaxed text-muted-foreground">
              The high-moat scorer flagged this opp as a fit for
              MacTech&rsquo;s strongest win profile (UFGS 25 / FRCS cyber
              clauses, set-aside fit, thin interested-vendors list) but
              didn&rsquo;t emit a one-sentence rationale. Open the score
              breakdown below for the component-level evidence.
            </p>
          )}
        </div>

        {hasAnyMeta && (
          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            {hasClauses && (
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Clauses cited
                </dt>
                <dd className="mt-1 flex flex-wrap gap-1">
                  {hm.clause_hits.map((c) => (
                    <ExplainLink key={c} slug={`clause:${c}`}>
                      <Badge tone="neutral">{c}</Badge>
                    </ExplainLink>
                  ))}
                </dd>
              </div>
            )}
            {hasClearance && (
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Top clearance
                </dt>
                <dd className="mt-1">
                  <Badge tone="neutral">{hm.top_clearance}</Badge>
                </dd>
              </div>
            )}
            {hasRoles && (
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Cleared roles
                </dt>
                <dd className="mt-1 flex flex-wrap gap-1">
                  {hm.role_hits.map((r) => (
                    <ExplainLink key={r} slug={`role:${r}`}>
                      <Badge tone="neutral">{r}</Badge>
                    </ExplainLink>
                  ))}
                </dd>
              </div>
            )}
          </dl>
        )}
      </div>
    </section>
  );
}

function PursuitPanel({
  opportunityId,
  pursuit,
  meFounderSlug
}: {
  opportunityId: string;
  pursuit: PursuitCardT | null;
  meFounderSlug: string | null;
}) {
  if (!pursuit) {
    return (
      <section className="rounded-md border border-dashed border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Capture pipeline
            </p>
            <p className="mt-1 text-sm text-foreground">
              Not in the pipeline yet. Add it to start tracking the pursuit.
            </p>
          </div>
          <form
            action={async () => {
              "use server";
              await createPursuit({
                opportunityId,
                stage: "lead",
                ownerFounderSlug: meFounderSlug
              });
            }}
          >
            <Button type="submit" variant="primary">
              Add to pipeline →
            </Button>
          </form>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-md border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Capture pipeline
            </p>
            <Badge tone={STAGE_TONE[pursuit.stage]}>
              {STAGE_LABEL[pursuit.stage]}
            </Badge>
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {pursuit.days_in_stage}d in stage
            </span>
          </div>
          <p className="mt-2 text-sm text-foreground">
            Owner:{" "}
            {pursuit.owner_founder_slug ? (
              <span className="font-medium">
                {pursuit.owner_founder_name ?? pursuit.owner_founder_slug}{" "}
                <span className="text-muted-foreground">@{pursuit.owner_founder_slug}</span>
              </span>
            ) : (
              <span className="italic text-muted-foreground">unassigned</span>
            )}
          </p>
          {pursuit.notes && (
            <p className="mt-2 max-w-2xl whitespace-pre-wrap text-sm leading-relaxed text-foreground">
              {pursuit.notes}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DetailStageButtons pursuit={pursuit} />
          <Link
            href={`/pursuits/${pursuit.id}/capture-package`}
            className="rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/15"
            title="Snapshot of everything CaptureOS knows about this pursuit — handoff to ProposalOS"
          >
            Capture Package →
          </Link>
          <LinkButton href="/pipeline" variant="secondary" size="sm">
            Open kanban →
          </LinkButton>
          <form
            action={async () => {
              "use server";
              await deletePursuit({
                pursuitId: pursuit.id,
                opportunityId
              });
            }}
          >
            <Button type="submit" variant="danger" size="sm" title="Remove from pipeline">
              Remove
            </Button>
          </form>
        </div>
      </div>
    </section>
  );
}

function DetailStageButtons({ pursuit }: { pursuit: PursuitCardT }) {
  const order: PursuitStage[] = [
    "lead",
    "qualify",
    "pursue",
    "propose",
    "submit"
  ];
  const idx = order.indexOf(pursuit.stage);
  const canRegress = idx > 0;
  const canAdvance = idx >= 0 && idx < order.length - 1;
  const canFinish = idx >= 1; // qualify or later

  return (
    <div className="flex items-center gap-1.5">
      {canRegress && (
        <DetailStageBtn
          pursuit={pursuit}
          stage={order[idx - 1]}
          label={`← ${STAGE_LABEL[order[idx - 1]]}`}
          variant="secondary"
        />
      )}
      {canAdvance && (
        <DetailStageBtn
          pursuit={pursuit}
          stage={order[idx + 1]}
          label={`${STAGE_LABEL[order[idx + 1]]} →`}
          variant="primary"
        />
      )}
      {canFinish && pursuit.stage !== "won" && (
        <DetailStageBtn pursuit={pursuit} stage="won" label="Won" variant="success" />
      )}
      {canFinish && pursuit.stage !== "lost" && (
        <DetailStageBtn pursuit={pursuit} stage="lost" label="Lost" variant="destructive" />
      )}
    </div>
  );
}

function DetailStageBtn({
  pursuit,
  stage,
  label,
  variant
}: {
  pursuit: PursuitCardT;
  stage: PursuitStage;
  label: string;
  variant: "secondary" | "primary" | "success" | "destructive";
}) {
  return (
    <form
      action={async () => {
        "use server";
        await updatePursuit({
          pursuitId: pursuit.id,
          opportunityId: pursuit.opportunity.id,
          stage
        });
      }}
    >
      <Button type="submit" variant={variant} size="sm">
        {label}
      </Button>
    </form>
  );
}

function DrafterPanel({
  opportunityId,
  drafts,
  noticeType
}: {
  opportunityId: string;
  drafts: DraftListResponse;
  noticeType: string | null;
}) {
  const isSourcesSought =
    noticeType?.toLowerCase().includes("sources sought") ?? false;

  return (
    <section className="rounded-md border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Proposal drafter
            {isSourcesSought && (
              <span className="ml-2 inline-flex items-center rounded-md border border-warning/20 bg-warning/10 px-1.5 py-0.5 text-[10px] font-medium text-warning">
                recommended for this notice
              </span>
            )}
          </p>
          <p className="mt-1 max-w-2xl text-sm text-foreground">
            {drafts.total === 0
              ? isSourcesSought
                ? "This is a Sources Sought notice — perfect for the AI drafter. Generate a starting response using your capability statements, past performance, and active teaming partners."
                : "Generate a Sources Sought–style capability response from this opportunity. Useful for white papers, RFI responses, or as a head start on a real proposal."
              : `${drafts.total} draft${drafts.total === 1 ? "" : "s"} on this opportunity. Open one to edit, or generate a new version.`}
          </p>
        </div>
        {drafts.items.length > 0 && (
          <LinkButton href={`/drafts/${drafts.items[0].id}`} variant="secondary" size="sm">
            Open latest draft →
          </LinkButton>
        )}
      </div>

      {drafts.items.length === 0 ? (
        <div className="mt-4">
          <StreamingDraftButton
            opportunityId={opportunityId}
            hasExistingDrafts={false}
            recommended={isSourcesSought}
          />
        </div>
      ) : (
        <>
          <ul className="mt-4 space-y-2 border-t border-border pt-3">
            {drafts.items.slice(0, 5).map((d) => (
              <li
                key={d.id}
                className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-xs"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <Badge tone="violet">v{d.version}</Badge>
                  <Badge tone={d.status === "submitted" ? "green" : "neutral"}>
                    {d.status}
                  </Badge>
                  <Link
                    href={`/drafts/${d.id}`}
                    className="truncate text-foreground hover:underline"
                  >
                    {d.title}
                  </Link>
                </div>
                <span className="shrink-0 tabular-nums text-[10px] text-muted-foreground">
                  {fmtDate(d.created_at)}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-3">
            <StreamingDraftButton
              opportunityId={opportunityId}
              hasExistingDrafts={true}
              recommended={false}
            />
          </div>
        </>
      )}
    </section>
  );
}

function ExplainRail({
  slug,
  explanation,
  oppId
}: {
  slug: string;
  explanation: TermExplanationResponse | null;
  oppId: string;
}) {
  return (
    <aside className="lg:sticky lg:top-6 lg:self-start" aria-label="Explain">
      <div className="rounded-lg border border-primary/20 bg-primary/10 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wide text-primary">
              Explain this
            </p>
            <h3 className="mt-1 text-base font-semibold text-foreground">
              {explanation?.label ?? slug}
            </h3>
          </div>
          <Link
            href={`/opportunities/${oppId}`}
            className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-card hover:text-foreground"
            aria-label="Close explanation"
            title="Close"
          >
            ✕
          </Link>
        </div>

        {explanation ? (
          <>
            <p className="mt-4 text-sm font-semibold leading-relaxed text-foreground">
              {explanation.summary}
            </p>
            <div className="mt-3 space-y-3 text-sm leading-relaxed text-foreground">
              {explanation.body
                .split(/\n{2,}/)
                .filter((p) => p.trim().length > 0)
                .map((para, i) => (
                  <p key={i}>{para}</p>
                ))}
            </div>
            <p className="mt-4 border-t border-primary/20 pt-3 text-[11px] text-muted-foreground">
              {explanation.cached
                ? "Cached. "
                : "Generated by Claude Haiku. Cached for next time. "}
              Plain-English explainer · click any underlined term to swap.
            </p>
          </>
        ) : (
          <p className="mt-4 text-sm text-foreground">
            Couldn&rsquo;t generate an explanation for{" "}
            <span className="font-mono text-xs">{slug}</span>. The Anthropic
            API may be unavailable; try again in a moment.
          </p>
        )}
      </div>

      <p className="mt-3 text-[11px] text-muted-foreground">
        Tip: any badge with a small <span className="text-primary">?</span>{" "}
        opens this rail with that term&rsquo;s explanation.
      </p>
    </aside>
  );
}

/* ── Ask Claude about this opp ──────────────────────────────────── */

const STARTER_LABELS: Record<string, string> = {
  should_we_pursue: "Should we pursue this?",
  incumbent: "Who's the likely incumbent?",
  win_probability: "What's our win probability?",
  must_haves: "What are the must-haves?",
  teaming: "Should we prime, sub, or team?"
};

const STARTER_ORDER = [
  "should_we_pursue",
  "incumbent",
  "win_probability",
  "must_haves",
  "teaming"
];

function AskPanel({
  opportunityId,
  questions,
  meFounderSlug: _meFounderSlug
}: {
  opportunityId: string;
  questions: QuestionListResponse;
  meFounderSlug: string | null;
}) {
  const recent = questions.items.slice(0, 5);

  return (
    <section className="rounded-lg border border-border bg-card p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-primary">
            Ask Claude about this opportunity
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Direct answers from your firm&rsquo;s data — capability statements, past
            performance, active partners, and the SAM description. Cap 200
            words per answer.
          </p>
        </div>
        {questions.total > 5 && (
          <span className="text-xs text-muted-foreground">
            {questions.total} total · showing 5 most recent
          </span>
        )}
      </div>

      <div className="mt-4">
        <AskStreamingPanel opportunityId={opportunityId} />
        <p className="sr-only">
          Saved to this opportunity for the team to see.
        </p>
      </div>

      {/* History */}
      {recent.length > 0 && (
        <ul className="mt-6 space-y-4 border-t border-border pt-5">
          {recent.map((q) => (
            <li key={q.id}>
              <QuestionCard q={q} opportunityId={opportunityId} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function QuestionCard({
  q,
  opportunityId
}: {
  q: QuestionOut;
  opportunityId: string;
}) {
  return (
    <article className="rounded-md border border-border bg-secondary p-4">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium text-foreground">
          <span className="text-primary">Q.</span> {q.question}
        </p>
        <form action={deleteOpportunityQuestion} className="shrink-0">
          <input type="hidden" name="id" value={q.id} />
          <input type="hidden" name="opportunity_id" value={opportunityId} />
          <button
            type="submit"
            className="rounded-md p-0.5 text-[10px] text-muted-foreground hover:text-destructive"
            title="Remove this Q&A"
            aria-label="Delete question"
          >
            ✕
          </button>
        </form>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-foreground">
        <span className="text-primary">A.</span> {q.answer}
      </p>
      <p className="mt-2 text-[11px] text-muted-foreground">
        {q.asked_by ? `${q.asked_by.full_name} · ` : ""}
        {fmtDate(q.created_at)}
        {q.model && ` · ${q.model}`}
        {q.output_tokens != null && ` · ${q.output_tokens} tokens`}
      </p>
    </article>
  );
}

/* ── Plain-English brief tab ─────────────────────────────────────── */

function BriefAndDescriptionPanel({
  opportunityId,
  description,
  brief,
  samResourceLinks,
  view
}: {
  opportunityId: string;
  description: OpportunityDetail["description"];
  brief: BriefOut | null;
  samResourceLinks: string[];
  /** "brief" | "raw" | null. Null falls through to the natural default:
   * brief when a brief row exists, raw when null. */
  view: "brief" | "raw" | null;
}) {
  const generateAction = generateOpportunityBrief.bind(null, opportunityId);
  // Default tab logic (pass 2): brief when a brief row exists, raw when
  // null. Honors the explicit search-param override.
  const activeView: "brief" | "raw" = view ?? (brief ? "brief" : "raw");

  // Label the raw tab by provenance. A BuildingConnected invite promoted into
  // an opportunity stores the invitation email as its description, so calling
  // it "SAM text" is wrong. Keyed on description.source, not notice_type.
  const isSam = description.source === "sam_gov";
  const rawLabel = isSam ? "Original SAM text" : "Original invitation";

  // Real tab pills (search-param-driven, server-component-friendly). The
  // active tab matches the score-bucket pill visual on the list page;
  // inactive uses a border-only treatment. Per brief §7.3.
  const briefHref = `?view=brief`;
  const rawHref = `?view=raw`;
  const briefTabClass =
    activeView === "brief"
      ? "rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
      : "rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:border-foreground/40";
  const rawTabClass =
    activeView === "raw"
      ? "rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
      : "rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:border-foreground/40";

  return (
    <Card>
      <header className="flex flex-wrap items-baseline justify-between gap-3 border-b border-border pb-3">
        <div className="flex gap-1" role="tablist" aria-label="Description view">
          <Link
            href={briefHref}
            scroll={false}
            aria-selected={activeView === "brief"}
            role="tab"
            className={briefTabClass}
          >
            Plain-English brief
          </Link>
          <Link
            href={rawHref}
            scroll={false}
            aria-selected={activeView === "raw"}
            role="tab"
            className={rawTabClass}
          >
            {rawLabel}
          </Link>
        </div>
        {/* Regenerate-brief affordance moved to the brief-panel footer
            next to the provenance line — see BriefBody. The header
            stays focused on the tab segmented-control. */}
      </header>

      {activeView === "brief" ? (
        <section
          role="tabpanel"
          aria-label="Plain-English brief"
          className="pt-4"
        >
          {brief ? (
            <BriefBody brief={brief} generateAction={generateAction} />
          ) : (
            <BriefEmpty
              description={description}
              generateAction={generateAction}
            />
          )}
        </section>
      ) : (
        <section
          role="tabpanel"
          aria-label={isSam ? "Original SAM description" : "Original invitation"}
          className="pt-4"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {isSam ? "Original SAM text" : "Original invitation email"}
          </p>
          {description.fetch_status === "fetched" && description.text ? (
            <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-secondary p-3 font-sans text-xs leading-relaxed text-foreground">
              {description.text.trim()}
            </pre>
          ) : description.fetch_status === "pending" ? (
            <p className="mt-3 text-sm text-muted-foreground">
              {isSam
                ? "Description text is queued for fetch from SAM.gov. The worker pulls it on the next 30-minute tick."
                : "No invitation text captured for this bid invite."}
            </p>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">
              No description text available for this notice.
            </p>
          )}

          {samResourceLinks.length > 0 && (
            <div className="mt-4 border-t border-border pt-3">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Attachments ({samResourceLinks.length})
              </p>
              <ul className="mt-2 space-y-1 text-sm">
                {samResourceLinks.map((url, i) => (
                  <li key={url}>
                    <a
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="break-all text-primary hover:underline"
                    >
                      Attachment {i + 1} →
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </Card>
  );
}

function BriefBody({
  brief,
  generateAction
}: {
  brief: BriefOut;
  generateAction: () => Promise<void>;
}) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wide text-primary">
          Scope
        </p>
        <p className="mt-1 text-base font-semibold leading-snug text-foreground">
          <AnnotatedProse text={brief.scope_one_sentence} />
        </p>
      </div>

      {brief.must_have_requirements.length > 0 && (
        <BriefList
          label="Must-have requirements"
          items={brief.must_have_requirements}
          tone="brand"
        />
      )}
      {brief.nice_to_have.length > 0 && (
        <BriefList
          label="Nice-to-haves"
          items={brief.nice_to_have}
          tone="neutral"
        />
      )}
      {brief.red_flags_for_small_biz.length > 0 && (
        <BriefList
          label="Red flags for a small business"
          items={brief.red_flags_for_small_biz}
          tone="amber"
        />
      )}
      {brief.suggested_team_roles.length > 0 && (
        <BriefList
          label="Suggested teaming"
          items={brief.suggested_team_roles}
          tone="violet"
        />
      )}

      {/* Provenance + regenerate affordance. Pass 2: regenerate moved
          from the tab header to here so it sits next to the content it
          mutates (brief §7.3). The tab header now stays focused on the
          tab segmented-control only. */}
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-border pt-3">
        <p className="text-[11px] text-muted-foreground">
          Auto-generated by {brief.model ?? "Claude"} from{" "}
          {brief.description_chars?.toLocaleString() ?? "?"} chars of SAM text ·{" "}
          Updated {fmtDate(brief.updated_at)}
        </p>
        <form action={generateAction}>
          <button
            type="submit"
            className="rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            title="Regenerate the brief from the current SAM description"
          >
            ↻ Regenerate brief
          </button>
        </form>
      </div>
    </div>
  );
}

function BriefList({
  label,
  items,
  tone
}: {
  label: string;
  items: string[];
  tone: "brand" | "neutral" | "amber" | "violet";
}) {
  // Tone names stay back-compat for callers; values resolve to semantic
  // tokens. Pass 2: `violet` routes to `text-muted-foreground` /
  // `bg-muted-foreground` per brief §11 Q2 — neutralizes the
  // teaming-roles section rather than pillar-coding it (avoids
  // introducing semantic load the layman BD lead has no legend for).
  const headTones: Record<string, string> = {
    brand: "text-primary",
    neutral: "text-muted-foreground",
    amber: "text-warning",
    violet: "text-muted-foreground"
  };
  const dotTones: Record<string, string> = {
    brand: "bg-primary",
    neutral: "bg-muted-foreground",
    amber: "bg-warning",
    violet: "bg-muted-foreground"
  };
  return (
    <div>
      <p
        className={`text-[11px] font-medium uppercase tracking-wide ${headTones[tone]}`}
      >
        {label}
      </p>
      <ul className="mt-2 space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm leading-relaxed">
            <span
              aria-hidden
              className={`mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full ${dotTones[tone]}`}
            />
            <span className="text-foreground">
              <AnnotatedProse text={item} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BriefEmpty({
  description,
  generateAction
}: {
  description: OpportunityDetail["description"];
  generateAction: () => Promise<void>;
}) {
  const hasText =
    description.fetch_status === "fetched" && !!description.text;
  return (
    <div className="rounded-md border border-dashed border-border bg-secondary p-5 text-center">
      <p className="text-sm font-medium text-foreground">
        No plain-English brief yet
      </p>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        {hasText ? (
          <>
            Generate a structured 30-second read of this opportunity — scope,
            must-haves, red flags, and teaming suggestions — in 10–20 seconds.
          </>
        ) : description.fetch_status === "pending" ? (
          <>
            The SAM description text hasn&rsquo;t been fetched yet. The worker
            pulls it on the next 30-minute tick; the brief will be available
            shortly after that.
          </>
        ) : (
          <>
            SAM didn&rsquo;t return any description text for this notice, so
            there&rsquo;s nothing to summarize. Try the attachments instead.
          </>
        )}
      </p>
      {hasText && (
        <form action={generateAction} className="mt-4">
          <Button type="submit" variant="primary">
            Generate brief →
          </Button>
        </form>
      )}
    </div>
  );
}

