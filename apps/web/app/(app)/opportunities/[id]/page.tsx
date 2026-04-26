import Link from "next/link";
import { notFound } from "next/navigation";
import {
  apiFetch,
  type AgencyIntelOut,
  type BriefOut,
  type DraftListResponse,
  type MeResponse,
  type OpportunityDetail,
  type PursuitCard as PursuitCardT,
  type PursuitStage,
  type QuestionListResponse,
  type QuestionOut,
  type TermExplanationResponse
} from "@/lib/api";
import { createPursuit, deletePursuit, updatePursuit } from "@/lib/pursuits";
import { generateSourcesSoughtDraft } from "@/lib/drafts";
import {
  askOpportunityQuestion,
  deleteOpportunityQuestion
} from "@/lib/ask";
import {
  deleteOpportunityBrief,
  generateOpportunityBrief
} from "@/lib/brief";
import { pullAgencyIntel } from "@/lib/agency-intel";
import {
  Badge,
  Card,
  ExplainLink,
  LinkButton,
  NaicsBadge,
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
  searchParams: Promise<{ explain?: string }>;
}) {
  const [{ id }, sp] = await Promise.all([params, searchParams]);
  const explainSlug = sp.explain?.trim() || null;

  let data: OpportunityDetail;
  try {
    data = await apiFetch<OpportunityDetail>(`/opportunities/${id}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  // Pursuit + me + drafts + Q&A + brief + agency intel + (optional)
  // explanation run in parallel. Brief, questions, and agency intel
  // legitimately 404/empty/timeout — caller swallows.
  // Agency intel uses a short timeout: if the cache is cold the API will
  // hit USASpending live (5-10s), and we don't want that to block page
  // render. Cache hits return in <100ms; cold misses fall through to the
  // "Pull agency intel" CTA which uses the explicit server action.
  const [me, pursuit, drafts, questions, brief, agencyIntel, explanation] =
    await Promise.all([
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
      apiFetch<AgencyIntelOut>(`/opportunities/${id}/agency-intel`, {
        timeoutMs: 4_000
      }).catch(() => null as AgencyIntelOut | null),
      explainSlug
        ? apiFetch<TermExplanationResponse>(
            `/explain/${encodeURIComponent(explainSlug)}`,
            { timeoutMs: 45_000 }
          ).catch(() => null as TermExplanationResponse | null)
        : Promise.resolve(null as TermExplanationResponse | null)
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
      <div>
        <Link
          href="/opportunities"
          className="text-xs text-neutral-500 hover:text-neutral-800"
        >
          ← All opportunities
        </Link>
      </div>

      {/* Header strip — full width */}
      <header className="rounded-md border border-neutral-200 bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-wider text-neutral-500">
              {opp.agency ?? "Agency unknown"}
            </p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-neutral-900">
              {opp.title}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
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
          </div>
          <div className="flex shrink-0 items-center gap-3">
            {data.score && <ScoreBadge score={data.score.score} />}
            {opp.sam_link && (
              <LinkButton href={opp.sam_link} external variant="primary">
                Open on SAM.gov →
              </LinkButton>
            )}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 text-sm">
          <Meta label="Posted" value={fmtDate(opp.posted_at)} />
          <Meta
            label="Deadline"
            value={fmtRelativeDays(opp.response_deadline, opp.days_until_deadline)}
          />
          <Meta
            label="Set-aside"
            value={
              opp.set_aside_description ?? opp.set_aside ?? (
                <span className="text-neutral-400">unrestricted</span>
              )
            }
          />
          <Meta
            label="Notice ID"
            value={<span className="break-all font-mono text-xs">{opp.notice_id}</span>}
          />
        </div>
      </header>

      {/* Pursuit / pipeline status strip */}
      <PursuitPanel
        opportunityId={opp.id}
        pursuit={pursuit}
        meFounderSlug={me.founder?.slug ?? null}
      />

      {/* Sources Sought drafter strip */}
      <DrafterPanel opportunityId={opp.id} drafts={drafts} noticeType={opp.notice_type} />

      {/* Ask-Claude panel — quickest path from "what is this" to an answer */}
      <AskPanel
        opportunityId={opp.id}
        questions={questions}
        meFounderSlug={me.founder?.slug ?? null}
      />

      {/* Two-column main: description (with brief tab) left, incumbent + capability right */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BriefAndDescriptionPanel
          opportunityId={opp.id}
          description={data.description}
          brief={brief}
          samResourceLinks={data.sam_resource_links}
        />

        <div className="space-y-4">
          <Card title="Incumbent intelligence">
            {data.incumbent && data.incumbent.name ? (
              <>
                <p className="text-base font-semibold text-neutral-900">
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
                          <span className="text-xs text-neutral-500">
                            {fmtDate(data.incumbent.exclusions.checked_at)}
                          </span>
                        </span>
                      )}
                    </Row>
                  )}
                </dl>
              </>
            ) : (
              <p className="text-sm text-neutral-600">
                No incumbent identified yet.{" "}
                {data.enrichment_notes ?? "Enrichment may still be pending."}
              </p>
            )}
          </Card>

          <Card title="MacTech capability matches">
            {data.capability_matches.length === 0 ? (
              <p className="text-sm text-neutral-600">
                No capability statements ranked. Either embeddings haven&rsquo;t populated
                yet or similarity is below threshold.
              </p>
            ) : (
              <ul className="space-y-3">
                {data.capability_matches.slice(0, 4).map((m) => (
                  <li key={m.id} className="border-b border-neutral-100 pb-3 last:border-b-0 last:pb-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-sm font-semibold text-neutral-900">{m.title}</p>
                      <Badge tone="blue">sim {m.similarity.toFixed(2)}</Badge>
                    </div>
                    <p className="mt-1 line-clamp-3 text-xs text-neutral-600">{m.summary}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {/* Agency intel — full-width strip below the 2-col main */}
      <AgencyIntelCard
        opportunityId={opp.id}
        agency={opp.agency}
        naics={opp.naics_code}
        intel={agencyIntel}
      />

      {/* Score + rationale — full-width */}
      {data.score ? (
        <section className="rounded-md border border-neutral-200 bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                Score
              </p>
              <div className="mt-1 flex items-baseline gap-2">
                <p className="text-4xl font-semibold tabular-nums text-neutral-900">
                  {data.score.score}
                </p>
                <p className="text-sm text-neutral-500">/ 100</p>
              </div>
              {data.score.assigned_founder_slug && (
                <p className="mt-2 text-xs text-neutral-500">
                  Assigned to{" "}
                  <span className="font-medium text-neutral-800">
                    @{data.score.assigned_founder_slug}
                  </span>
                </p>
              )}
              {data.score.scored_at && (
                <p className="mt-1 text-[11px] text-neutral-400">
                  Scored {fmtDate(data.score.scored_at)}
                </p>
              )}
            </div>
            {data.score.why_it_matters && (
              <div className="min-w-0 flex-1 lg:max-w-xl">
                <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                  Why this matters
                </p>
                <p className="mt-1 text-sm leading-relaxed text-neutral-800">
                  {data.score.why_it_matters}
                </p>
                {data.score.why_it_matters_model && (
                  <p className="mt-2 text-[10px] text-neutral-400">
                    via {data.score.why_it_matters_model}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="mt-5 border-t border-neutral-200 pt-4">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                Score breakdown
              </p>
              <p className="text-[11px] text-neutral-400">
                Hover any component for the scoring rule.
              </p>
            </div>
            <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(data.score.breakdown).map(([k, v]) => {
                const max = SCORE_COMPONENT_MAX[k];
                const pct = max ? Math.min(100, Math.max(0, (v / max) * 100)) : 0;
                const help = SCORE_COMPONENT_HELP[k];
                return (
                  <li
                    key={k}
                    title={help}
                    className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 transition-colors hover:border-brand-300 hover:bg-white"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <ExplainLink
                        slug={`score_component:${k}`}
                        className="-mx-1 px-1"
                      >
                        <span className="text-xs text-neutral-700">
                          {SCORE_COMPONENT_LABELS[k] ?? k}
                        </span>
                      </ExplainLink>
                      <span className="tabular-nums text-sm font-medium text-neutral-900">
                        {v}
                        {max && (
                          <span className="text-[10px] text-neutral-400"> / {max}</span>
                        )}
                      </span>
                    </div>
                    {max && (
                      <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-neutral-200">
                        <div
                          className="h-full rounded-full bg-neutral-700"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    )}
                    {help && (
                      <p className="mt-1.5 line-clamp-2 text-[10px] leading-snug text-neutral-500">
                        {help}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
      ) : (
        <Card title="Score">
          <p className="text-sm text-neutral-600">
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
      <dt className="text-[11px] uppercase tracking-wider text-neutral-500">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-neutral-500">{label}</p>
      <p className="mt-0.5">{value}</p>
    </div>
  );
}

const PURSUIT_STAGE_TONE: Record<PursuitStage, "neutral" | "blue" | "amber" | "violet" | "green" | "red"> = {
  lead: "neutral",
  qualify: "blue",
  pursue: "blue",
  propose: "amber",
  submit: "violet",
  won: "green",
  lost: "red"
};

const PURSUIT_STAGE_LABEL: Record<PursuitStage, string> = {
  lead: "Lead",
  qualify: "Qualify",
  pursue: "Pursue",
  propose: "Propose",
  submit: "Submit",
  won: "Won",
  lost: "Lost"
};

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
      <section className="rounded-md border border-dashed border-neutral-300 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">
              Capture pipeline
            </p>
            <p className="mt-1 text-sm text-neutral-700">
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
            <button
              type="submit"
              className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-800"
            >
              Add to pipeline →
            </button>
          </form>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-md border border-neutral-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">
              Capture pipeline
            </p>
            <Badge tone={PURSUIT_STAGE_TONE[pursuit.stage]}>
              {PURSUIT_STAGE_LABEL[pursuit.stage]}
            </Badge>
            <span className="text-[11px] text-neutral-500 tabular-nums">
              {pursuit.days_in_stage}d in stage
            </span>
          </div>
          <p className="mt-2 text-sm text-neutral-700">
            Owner:{" "}
            {pursuit.owner_founder_slug ? (
              <span className="font-medium">
                {pursuit.owner_founder_name ?? pursuit.owner_founder_slug}{" "}
                <span className="text-neutral-500">@{pursuit.owner_founder_slug}</span>
              </span>
            ) : (
              <span className="italic text-neutral-500">unassigned</span>
            )}
          </p>
          {pursuit.notes && (
            <p className="mt-2 max-w-2xl whitespace-pre-wrap text-sm leading-relaxed text-neutral-700">
              {pursuit.notes}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DetailStageButtons pursuit={pursuit} />
          <Link
            href="/pipeline"
            className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:border-neutral-500"
          >
            Open kanban →
          </Link>
          <form
            action={async () => {
              "use server";
              await deletePursuit({
                pursuitId: pursuit.id,
                opportunityId
              });
            }}
          >
            <button
              type="submit"
              className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs text-neutral-500 hover:border-red-300 hover:text-red-700"
              title="Remove from pipeline"
            >
              Remove
            </button>
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
          label={`← ${PURSUIT_STAGE_LABEL[order[idx - 1]]}`}
          variant="ghost"
        />
      )}
      {canAdvance && (
        <DetailStageBtn
          pursuit={pursuit}
          stage={order[idx + 1]}
          label={`${PURSUIT_STAGE_LABEL[order[idx + 1]]} →`}
          variant="primary"
        />
      )}
      {canFinish && pursuit.stage !== "won" && (
        <DetailStageBtn pursuit={pursuit} stage="won" label="Won" variant="green" />
      )}
      {canFinish && pursuit.stage !== "lost" && (
        <DetailStageBtn pursuit={pursuit} stage="lost" label="Lost" variant="red" />
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
  variant: "ghost" | "primary" | "green" | "red";
}) {
  const cls =
    variant === "primary"
      ? "rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
      : variant === "green"
      ? "rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
      : variant === "red"
      ? "rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
      : "rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:border-neutral-500";

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
      <button type="submit" className={cls}>
        {label}
      </button>
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
  const action = generateSourcesSoughtDraft.bind(null, opportunityId);

  return (
    <section className="rounded-md border border-neutral-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-neutral-500">
            Proposal drafter
            {isSourcesSought && (
              <span className="ml-2 inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                recommended for this notice
              </span>
            )}
          </p>
          <p className="mt-1 max-w-2xl text-sm text-neutral-700">
            {drafts.total === 0
              ? isSourcesSought
                ? "This is a Sources Sought notice — perfect for the AI drafter. Generate a starting response using your capability statements, past performance, and active teaming partners."
                : "Generate a Sources Sought–style capability response from this opportunity. Useful for white papers, RFI responses, or as a head start on a real proposal."
              : `${drafts.total} draft${drafts.total === 1 ? "" : "s"} on this opportunity. Open one to edit, or generate a new version.`}
          </p>
        </div>
        {drafts.items.length > 0 && (
          <Link
            href={`/drafts/${drafts.items[0].id}`}
            className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:border-neutral-500"
          >
            Open latest draft →
          </Link>
        )}
      </div>

      {drafts.items.length === 0 ? (
        <form action={action} className="mt-4 space-y-3">
          <label className="block">
            <span className="block text-[11px] uppercase tracking-wider text-neutral-500">
              Custom instructions (optional)
            </span>
            <textarea
              name="custom_instructions"
              rows={2}
              placeholder="e.g. Lead with cybersecurity past performance. Tone: formal."
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-xs shadow-sm focus:border-neutral-500 focus:outline-none"
            />
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              className="rounded-md border border-neutral-900 bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
            >
              Draft response →
            </button>
            <span className="text-[11px] text-neutral-400">
              Takes 20–60s. Uses Claude Sonnet 4.6.
            </span>
          </div>
        </form>
      ) : (
        <ul className="mt-4 space-y-2 border-t border-neutral-100 pt-3">
          {drafts.items.slice(0, 5).map((d) => (
            <li
              key={d.id}
              className="flex items-center justify-between gap-3 rounded-md border border-neutral-100 px-3 py-2 text-xs"
            >
              <div className="flex min-w-0 items-center gap-2">
                <Badge tone="violet">v{d.version}</Badge>
                <Badge tone={d.status === "submitted" ? "green" : "neutral"}>
                  {d.status}
                </Badge>
                <Link
                  href={`/drafts/${d.id}`}
                  className="truncate text-neutral-800 hover:underline"
                >
                  {d.title}
                </Link>
              </div>
              <span className="shrink-0 tabular-nums text-[10px] text-neutral-400">
                {fmtDate(d.created_at)}
              </span>
            </li>
          ))}
          <form action={action} className="pt-2">
            <button
              type="submit"
              className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:border-neutral-500"
            >
              + Generate new version
            </button>
          </form>
        </ul>
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
      <div className="rounded-lg border border-brand-200 bg-brand-50 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wide text-brand-700">
              Explain this
            </p>
            <h3 className="mt-1 text-base font-semibold text-neutral-900">
              {explanation?.label ?? slug}
            </h3>
          </div>
          <Link
            href={`/opportunities/${oppId}`}
            className="shrink-0 rounded-md p-1 text-neutral-500 hover:bg-white hover:text-neutral-800"
            aria-label="Close explanation"
            title="Close"
          >
            ✕
          </Link>
        </div>

        {explanation ? (
          <>
            <p className="mt-4 text-sm font-semibold leading-relaxed text-neutral-900">
              {explanation.summary}
            </p>
            <div className="mt-3 space-y-3 text-sm leading-relaxed text-neutral-700">
              {explanation.body
                .split(/\n{2,}/)
                .filter((p) => p.trim().length > 0)
                .map((para, i) => (
                  <p key={i}>{para}</p>
                ))}
            </div>
            <p className="mt-4 border-t border-brand-200 pt-3 text-[11px] text-neutral-500">
              {explanation.cached
                ? "Cached. "
                : "Generated by Claude Haiku. Cached for next time. "}
              Plain-English explainer · click any underlined term to swap.
            </p>
          </>
        ) : (
          <p className="mt-4 text-sm text-neutral-700">
            Couldn&rsquo;t generate an explanation for{" "}
            <span className="font-mono text-xs">{slug}</span>. The Anthropic
            API may be unavailable; try again in a moment.
          </p>
        )}
      </div>

      <p className="mt-3 text-[11px] text-neutral-500">
        Tip: any badge with a small <span className="text-brand-700">?</span>{" "}
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
  meFounderSlug
}: {
  opportunityId: string;
  questions: QuestionListResponse;
  meFounderSlug: string | null;
}) {
  const action = askOpportunityQuestion.bind(null, opportunityId);
  const recent = questions.items.slice(0, 5);

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-brand-700">
            Ask Claude about this opportunity
          </p>
          <p className="mt-1 text-sm text-neutral-600">
            Direct answers from your firm's data — capability statements, past
            performance, active partners, and the SAM description. Cap 200
            words per answer.
          </p>
        </div>
        {questions.total > 5 && (
          <span className="text-xs text-neutral-500">
            {questions.total} total · showing 5 most recent
          </span>
        )}
      </div>

      {/* Starter buttons + freeform form */}
      <form action={action} className="mt-4 space-y-3">
        <div className="flex flex-wrap gap-2">
          {STARTER_ORDER.map((kind) => (
            <button
              key={kind}
              type="submit"
              name="starter_kind"
              value={kind}
              className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 transition-colors hover:border-brand-500 hover:text-brand-800"
              title={
                questions.starters?.[kind] ??
                STARTER_LABELS[kind] ??
                kind
              }
            >
              {STARTER_LABELS[kind] ?? kind}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-stretch gap-2">
          <input
            type="hidden"
            name="me_founder_slug"
            value={meFounderSlug ?? ""}
          />
          <input
            name="question"
            placeholder="Or type your own question…"
            maxLength={1000}
            className="min-w-0 flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <button
            type="submit"
            className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
          >
            Ask →
          </button>
        </div>
        <p className="text-[11px] text-neutral-500">
          Takes 5–15 seconds. Answer is saved to this opportunity for the team
          to see.
        </p>
      </form>

      {/* History */}
      {recent.length > 0 && (
        <ul className="mt-6 space-y-4 border-t border-neutral-100 pt-5">
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
    <article className="rounded-md border border-neutral-100 bg-neutral-50 p-4">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium text-neutral-800">
          <span className="text-brand-700">Q.</span> {q.question}
        </p>
        <form action={deleteOpportunityQuestion} className="shrink-0">
          <input type="hidden" name="id" value={q.id} />
          <input type="hidden" name="opportunity_id" value={opportunityId} />
          <button
            type="submit"
            className="rounded-md p-0.5 text-[10px] text-neutral-400 hover:text-red-700"
            title="Remove this Q&A"
            aria-label="Delete question"
          >
            ✕
          </button>
        </form>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-neutral-800">
        <span className="text-brand-700">A.</span> {q.answer}
      </p>
      <p className="mt-2 text-[11px] text-neutral-400">
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
  samResourceLinks
}: {
  opportunityId: string;
  description: OpportunityDetail["description"];
  brief: BriefOut | null;
  samResourceLinks: string[];
}) {
  const generateAction = generateOpportunityBrief.bind(null, opportunityId);

  return (
    <Card>
      <header className="flex flex-wrap items-baseline justify-between gap-3 border-b border-neutral-100 pb-3">
        <div className="flex gap-1" role="tablist" aria-label="Description view">
          {/* Use anchor links with hash so the page scrolls to the section
              without a server roundtrip. The "active" tab is implicit —
              the user toggles via :target on the destination panel. */}
          <a
            href={`#brief-${opportunityId}`}
            className="rounded-md border border-brand-300 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-800 hover:bg-brand-100"
            role="tab"
          >
            Plain-English brief
          </a>
          <a
            href={`#raw-${opportunityId}`}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 hover:border-neutral-500"
            role="tab"
          >
            Original SAM text
          </a>
        </div>
        {brief && (
          <form action={generateAction}>
            <button
              type="submit"
              className="rounded-md px-2 py-1 text-[11px] text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800"
              title="Regenerate the brief from the current SAM description"
            >
              ↻ Regenerate brief
            </button>
          </form>
        )}
      </header>

      {/* Brief panel — primary, lives at #brief-{id} */}
      <section
        id={`brief-${opportunityId}`}
        role="tabpanel"
        aria-label="Plain-English brief"
        className="pt-4"
      >
        {brief ? (
          <BriefBody brief={brief} />
        ) : (
          <BriefEmpty
            description={description}
            generateAction={generateAction}
          />
        )}
      </section>

      {/* Raw panel — secondary, lives at #raw-{id}. Hidden visually below
          the brief, so #raw anchor scroll just reveals further down. */}
      <section
        id={`raw-${opportunityId}`}
        role="tabpanel"
        aria-label="Original SAM description"
        className="mt-6 border-t border-neutral-100 pt-4"
      >
        <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">
          Original SAM text
        </p>
        {description.fetch_status === "fetched" && description.text ? (
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-neutral-200 bg-neutral-50 p-3 font-sans text-xs leading-relaxed text-neutral-700">
            {description.text.trim()}
          </pre>
        ) : description.fetch_status === "pending" ? (
          <p className="mt-3 text-sm text-neutral-600">
            Description text is queued for fetch from SAM.gov. The worker pulls
            it on the next 30-minute tick.
          </p>
        ) : (
          <p className="mt-3 text-sm text-neutral-600">
            No description text available for this notice.
          </p>
        )}

        {samResourceLinks.length > 0 && (
          <div className="mt-4 border-t border-neutral-100 pt-3">
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">
              Attachments ({samResourceLinks.length})
            </p>
            <ul className="mt-2 space-y-1 text-sm">
              {samResourceLinks.map((url, i) => (
                <li key={url}>
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="break-all text-brand-700 hover:underline"
                  >
                    Attachment {i + 1} →
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </Card>
  );
}

function BriefBody({ brief }: { brief: BriefOut }) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wide text-brand-700">
          Scope
        </p>
        <p className="mt-1 text-base font-semibold leading-snug text-neutral-900">
          {brief.scope_one_sentence}
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

      <p className="text-[11px] text-neutral-400">
        Auto-generated by {brief.model ?? "Claude"} from{" "}
        {brief.description_chars?.toLocaleString() ?? "?"} chars of SAM text ·{" "}
        Updated {fmtDate(brief.updated_at)}
      </p>
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
  const headTones: Record<string, string> = {
    brand: "text-brand-700",
    neutral: "text-neutral-600",
    amber: "text-amber-700",
    violet: "text-violet-700"
  };
  const dotTones: Record<string, string> = {
    brand: "bg-brand-500",
    neutral: "bg-neutral-400",
    amber: "bg-amber-500",
    violet: "bg-violet-500"
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
            <span className="text-neutral-800">{item}</span>
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
    <div className="rounded-md border border-dashed border-neutral-300 bg-neutral-50 p-5 text-center">
      <p className="text-sm font-medium text-neutral-800">
        No plain-English brief yet
      </p>
      <p className="mt-2 text-sm leading-relaxed text-neutral-600">
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
          <button
            type="submit"
            className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
          >
            Generate brief →
          </button>
        </form>
      )}
    </div>
  );
}

/* ── Agency intel card ───────────────────────────────────────────── */

function AgencyIntelCard({
  opportunityId,
  agency,
  naics,
  intel
}: {
  opportunityId: string;
  agency: string | null;
  naics: string | null;
  intel: AgencyIntelOut | null;
}) {
  const action = pullAgencyIntel.bind(null, opportunityId);

  if (!agency || !naics) {
    return null; // Nothing to query without both fields.
  }

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-brand-700">
            Agency intel
          </p>
          <p className="mt-1 text-sm text-neutral-600">
            How {agency.split(".")[0]} has spent under NAICS {naics} in the
            last 12 months. Pulled from USASpending; cached 7 days.
          </p>
        </div>
        {intel && (
          <form action={action}>
            <button
              type="submit"
              className="rounded-md px-2 py-1 text-[11px] text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800"
              title="Re-fetch from USASpending. Takes 5–10 seconds."
            >
              ↻ Refresh
            </button>
          </form>
        )}
      </div>

      {!intel ? (
        <AgencyIntelEmpty action={action} />
      ) : intel.lookup_failed ? (
        <AgencyIntelFailure intel={intel} action={action} />
      ) : intel.award_count === 0 ? (
        <AgencyIntelNoMatches intel={intel} />
      ) : (
        <AgencyIntelBody intel={intel} />
      )}
    </section>
  );
}

function AgencyIntelEmpty({
  action
}: {
  action: () => Promise<void>;
}) {
  return (
    <div className="mt-4 rounded-md border border-dashed border-neutral-300 bg-neutral-50 p-5 text-center">
      <p className="text-sm font-medium text-neutral-800">
        Agency intel not loaded yet
      </p>
      <p className="mt-2 text-sm text-neutral-600">
        Click below to pull spending history from USASpending.gov for this
        agency + NAICS combination. Takes 5–10 seconds the first time;
        subsequent loads are instant for 7 days.
      </p>
      <form action={action} className="mt-4">
        <button
          type="submit"
          className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
        >
          Pull agency intel →
        </button>
      </form>
    </div>
  );
}

function AgencyIntelFailure({
  intel,
  action
}: {
  intel: AgencyIntelOut;
  action: () => Promise<void>;
}) {
  return (
    <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
      <p className="font-medium">USASpending lookup didn&rsquo;t resolve.</p>
      <p className="mt-1 text-xs">
        {intel.failure_note ??
          "The agency name may not match a USASpending toptier exactly."}
      </p>
      <form action={action} className="mt-3">
        <button
          type="submit"
          className="rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-900 hover:border-amber-500"
        >
          Retry
        </button>
      </form>
    </div>
  );
}

function AgencyIntelNoMatches({ intel }: { intel: AgencyIntelOut }) {
  return (
    <p className="mt-4 text-sm text-neutral-600">
      USASpending returned <strong className="text-neutral-900">0 awards</strong>{" "}
      for {intel.agency_name} under NAICS {intel.naics_code} in the last{" "}
      {intel.lookback_days} days. Either this agency hasn&rsquo;t bought
      under this NAICS recently, or the agency name doesn&rsquo;t match a
      USASpending toptier exactly.
    </p>
  );
}

function AgencyIntelBody({ intel }: { intel: AgencyIntelOut }) {
  return (
    <div className="mt-5 space-y-5">
      {/* Top-line stats */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <IntelStat
          label="Awards (12mo)"
          value={intel.award_count.toLocaleString()}
          hint={
            intel.sample_size && intel.sample_size < intel.award_count
              ? `top ${intel.sample_size} sampled`
              : undefined
          }
        />
        <IntelStat
          label="Total obligated"
          value={
            intel.total_obligated != null
              ? fmtMoney(intel.total_obligated)
              : "—"
          }
          hint="across the sample"
        />
        <IntelStat
          label="Average award"
          value={
            intel.avg_award_value != null ? fmtMoney(intel.avg_award_value) : "—"
          }
        />
        <IntelStat
          label="Median award"
          value={
            intel.median_award_value != null
              ? fmtMoney(intel.median_award_value)
              : "—"
          }
          hint="less skewed by outliers"
        />
      </div>

      {/* Top recipients */}
      {intel.top_recipients.length > 0 && (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
            Top recipients
          </p>
          <ol className="mt-2 space-y-1.5">
            {intel.top_recipients.map((r, i) => (
              <li
                key={`${r.name}-${i}`}
                className="flex items-baseline justify-between gap-3 text-sm"
              >
                <span className="flex min-w-0 items-baseline gap-2">
                  <span className="text-neutral-400 tabular-nums">
                    {i + 1}.
                  </span>
                  <span className="truncate font-medium text-neutral-900">
                    {r.name}
                  </span>
                  <span className="shrink-0 text-[11px] text-neutral-500 tabular-nums">
                    {r.award_count} {r.award_count === 1 ? "award" : "awards"}
                  </span>
                </span>
                <span className="shrink-0 tabular-nums font-semibold text-neutral-800">
                  {fmtMoney(r.total)}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <p className="border-t border-neutral-100 pt-3 text-[11px] text-neutral-400">
        Refreshed {fmtDate(intel.refreshed_at)} ·{" "}
        {intel.is_fresh
          ? `cache hit (${Math.round(intel.cache_age_hours)}h old)`
          : "stale, refresh on next view"}{" "}
        · Source: USASpending.gov
      </p>
    </div>
  );
}

function IntelStat({
  label,
  value,
  hint
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-neutral-100 bg-neutral-50 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-neutral-500">
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-neutral-900">
        {value}
      </p>
      {hint && <p className="text-[10px] text-neutral-500">{hint}</p>}
    </div>
  );
}
