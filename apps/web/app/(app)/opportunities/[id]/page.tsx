import Link from "next/link";
import { notFound } from "next/navigation";
import {
  apiFetch,
  type MeResponse,
  type OpportunityDetail,
  type PursuitCard as PursuitCardT,
  type PursuitStage
} from "@/lib/api";
import { createPursuit, deletePursuit, updatePursuit } from "@/lib/pursuits";
import {
  Badge,
  Card,
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

export default async function OpportunityDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let data: OpportunityDetail;
  try {
    data = await apiFetch<OpportunityDetail>(`/opportunities/${id}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  // Pursuit + me run in parallel; pursuit may legitimately 404 if there's no
  // pipeline entry for this opp yet — swallow that.
  const [me, pursuit] = await Promise.all([
    apiFetch<MeResponse>("/me"),
    apiFetch<PursuitCardT>(`/pursuits/by-opportunity/${id}`).catch(
      () => null as PursuitCardT | null
    )
  ]);

  const opp = data.opportunity;

  return (
    <div className="space-y-6">
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
              <NoticeTypeBadge type={opp.notice_type} />
              <SetAsideBadge code={opp.set_aside} />
              {opp.naics_code && <Badge tone="neutral">NAICS {opp.naics_code}</Badge>}
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
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">
              Score breakdown
            </p>
            <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(data.score.breakdown).map(([k, v]) => {
                const max = SCORE_COMPONENT_MAX[k];
                const pct = max ? Math.min(100, Math.max(0, (v / max) * 100)) : 0;
                return (
                  <li
                    key={k}
                    className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-xs text-neutral-600">
                        {SCORE_COMPONENT_LABELS[k] ?? k}
                      </span>
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
