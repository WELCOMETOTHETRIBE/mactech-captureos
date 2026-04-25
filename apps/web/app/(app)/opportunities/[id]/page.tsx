import Link from "next/link";
import { notFound } from "next/navigation";
import {
  apiFetch,
  type DraftListResponse,
  type MeResponse,
  type OpportunityDetail,
  type PursuitCard as PursuitCardT,
  type PursuitStage,
  type TermExplanationResponse
} from "@/lib/api";
import { createPursuit, deletePursuit, updatePursuit } from "@/lib/pursuits";
import { generateSourcesSoughtDraft } from "@/lib/drafts";
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

  // Pursuit + me + drafts + (optional) explanation run in parallel.
  const [me, pursuit, drafts, explanation] = await Promise.all([
    apiFetch<MeResponse>("/me"),
    apiFetch<PursuitCardT>(`/pursuits/by-opportunity/${id}`).catch(
      () => null as PursuitCardT | null
    ),
    apiFetch<DraftListResponse>(`/opportunities/${id}/drafts`).catch(
      () => ({ total: 0, items: [] }) as DraftListResponse
    ),
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

      {/* Two-column main: description left, incumbent + capability right */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Description">
          {data.description.fetch_status === "fetched" && data.description.text ? (
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-neutral-800">
              {data.description.text.trim()}
            </pre>
          ) : data.description.fetch_status === "pending" ? (
            <p className="text-sm text-neutral-600">
              Description text is queued for fetch from SAM.gov. The worker pulls it on the
              next 30-minute tick.
            </p>
          ) : (
            <p className="text-sm text-neutral-600">
              No description text available for this notice.
            </p>
          )}
          {data.sam_resource_links.length > 0 && (
            <div className="mt-4 border-t border-neutral-200 pt-3">
              <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                Attachments ({data.sam_resource_links.length})
              </p>
              <ul className="mt-2 space-y-1 text-sm">
                {data.sam_resource_links.map((url, i) => (
                  <li key={url}>
                    <a
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="break-all text-blue-700 hover:underline"
                    >
                      Attachment {i + 1} →
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

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
