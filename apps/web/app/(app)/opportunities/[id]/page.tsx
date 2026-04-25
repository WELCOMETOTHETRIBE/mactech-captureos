import Link from "next/link";
import { notFound } from "next/navigation";
import { apiFetch, type OpportunityDetail } from "@/lib/api";
import {
  Badge,
  Card,
  LinkButton,
  NoticeTypeBadge,
  PageHeader,
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
