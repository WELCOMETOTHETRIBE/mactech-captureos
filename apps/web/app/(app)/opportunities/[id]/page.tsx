import Link from "next/link";
import { notFound } from "next/navigation";
import { apiFetch, type OpportunityDetail } from "@/lib/api";

export const dynamic = "force-dynamic";

function fmtMoney(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n.toFixed(0)}`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  });
}

function fmtDeadline(iso: string | null, days: number | null): string {
  if (!iso) return "no deadline set";
  const d = new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  });
  if (days == null) return d;
  if (days < 0) return `${d} (passed ${-days}d ago)`;
  if (days === 0) return `${d} (today)`;
  if (days === 1) return `${d} (1 day left)`;
  return `${d} (${days} days left)`;
}

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
  const meta = [
    opp.notice_type,
    opp.set_aside_description ?? opp.set_aside,
    opp.naics_code && `NAICS ${opp.naics_code}`,
    opp.solicitation_number && `Sol# ${opp.solicitation_number}`
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-6">
      <div>
        <Link href="/dashboard" className="text-xs text-neutral-500 hover:text-neutral-800">
          ← Dashboard
        </Link>
      </div>

      {/* Header strip */}
      <header className="rounded-md border border-neutral-200 bg-white p-5">
        <p className="text-xs uppercase tracking-wider text-neutral-500">
          {opp.agency ?? "Agency unknown"}
        </p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight">{opp.title}</h1>
        <p className="mt-2 text-xs text-neutral-500">{meta}</p>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 text-sm">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">Posted</p>
            <p className="mt-0.5 tabular-nums">{fmtDate(opp.posted_at)}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">Deadline</p>
            <p className="mt-0.5 tabular-nums">
              {fmtDeadline(opp.response_deadline, opp.days_until_deadline)}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">Notice ID</p>
            <p className="mt-0.5 break-all font-mono text-xs">{opp.notice_id}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">SAM.gov</p>
            <p className="mt-0.5">
              {opp.sam_link ? (
                <a
                  href={opp.sam_link}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-700 hover:underline"
                >
                  Open →
                </a>
              ) : (
                "—"
              )}
            </p>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* LEFT: description */}
        <section className="lg:col-span-5 space-y-4">
          <div className="rounded-md border border-neutral-200 bg-white p-5">
            <h2 className="text-xs uppercase tracking-wider text-neutral-500">
              Description
            </h2>
            {data.description.fetch_status === "fetched" && data.description.text ? (
              <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-relaxed text-neutral-800">
                {data.description.text.trim()}
              </pre>
            ) : data.description.fetch_status === "pending" ? (
              <p className="mt-3 text-sm text-neutral-600">
                Description text is queued for fetch from SAM.gov. The worker pulls it on the
                next 30-minute tick.
              </p>
            ) : (
              <p className="mt-3 text-sm text-neutral-600">
                No description text was returned by SAM.gov for this notice.
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
                        className="text-blue-700 hover:underline break-all"
                      >
                        Attachment {i + 1} →
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>

        {/* CENTER: incumbent + capability matches */}
        <section className="lg:col-span-4 space-y-4">
          <div className="rounded-md border border-neutral-200 bg-white p-5">
            <h2 className="text-xs uppercase tracking-wider text-neutral-500">
              Incumbent intelligence
            </h2>
            {data.incumbent && data.incumbent.name ? (
              <>
                <p className="mt-3 text-base font-semibold text-neutral-900">
                  {data.incumbent.name}
                </p>
                <dl className="mt-2 grid grid-cols-1 gap-1.5 text-sm">
                  {data.incumbent.uei && (
                    <Row label="UEI">
                      <span className="font-mono text-xs">{data.incumbent.uei}</span>
                    </Row>
                  )}
                  {data.incumbent.contract_amount != null && (
                    <Row label="Cumulative obligations">
                      {fmtMoney(data.incumbent.contract_amount)}
                    </Row>
                  )}
                  {data.incumbent.contract_end_date && (
                    <Row label="Contract end date">
                      {fmtDate(data.incumbent.contract_end_date)}
                    </Row>
                  )}
                  {data.incumbent.exclusions && (
                    <Row label="Exclusions">
                      {data.incumbent.exclusions.is_excluded ? (
                        <span className="text-red-600 font-medium">
                          ON DEBARMENT LIST
                        </span>
                      ) : (
                        <span className="text-emerald-700">
                          Clean (
                          <span className="text-neutral-500">
                            checked {fmtDate(data.incumbent.exclusions.checked_at)}
                          </span>
                          )
                        </span>
                      )}
                    </Row>
                  )}
                </dl>
              </>
            ) : (
              <p className="mt-3 text-sm text-neutral-600">
                No incumbent identified yet.{" "}
                {data.enrichment_notes ?? "Enrichment may still be pending."}
              </p>
            )}
          </div>

          <div className="rounded-md border border-neutral-200 bg-white p-5">
            <h2 className="text-xs uppercase tracking-wider text-neutral-500">
              MacTech capability matches
            </h2>
            {data.capability_matches.length === 0 ? (
              <p className="mt-3 text-sm text-neutral-600">
                No capability statements ranked. Either embeddings haven&rsquo;t populated yet
                or the similarity is below threshold.
              </p>
            ) : (
              <ul className="mt-3 space-y-3">
                {data.capability_matches.slice(0, 3).map((m) => (
                  <li key={m.id}>
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-sm font-semibold text-neutral-900">{m.title}</p>
                      <span className="text-[11px] tabular-nums text-neutral-500">
                        sim {m.similarity.toFixed(2)}
                      </span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-neutral-600">{m.summary}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        {/* RIGHT: score + actions */}
        <aside className="lg:col-span-3 space-y-4">
          {data.score ? (
            <div className="rounded-md border border-neutral-200 bg-white p-5">
              <h2 className="text-xs uppercase tracking-wider text-neutral-500">Score</h2>
              <p className="mt-2 text-4xl font-semibold tabular-nums">{data.score.score}</p>
              <p className="text-xs text-neutral-500">/ 100</p>
              <ul className="mt-4 space-y-1 text-xs">
                {Object.entries(data.score.breakdown).map(([k, v]) => (
                  <li key={k} className="flex justify-between">
                    <span className="text-neutral-600">
                      {SCORE_COMPONENT_LABELS[k] ?? k}
                    </span>
                    <span className="tabular-nums">{v}</span>
                  </li>
                ))}
              </ul>
              {data.score.assigned_founder_slug && (
                <p className="mt-4 border-t border-neutral-200 pt-3 text-xs text-neutral-500">
                  Assigned to{" "}
                  <span className="font-medium text-neutral-800">
                    {data.score.assigned_founder_slug}
                  </span>
                </p>
              )}
              {data.score.why_it_matters && (
                <div className="mt-3 border-t border-neutral-200 pt-3">
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
          ) : (
            <div className="rounded-md border border-neutral-200 bg-white p-5 text-sm text-neutral-600">
              Not scored yet. Scoring runs every 20 minutes.
            </div>
          )}

          <div className="rounded-md border border-neutral-200 bg-white p-5">
            <h2 className="text-xs uppercase tracking-wider text-neutral-500">Actions</h2>
            <p className="mt-3 text-sm text-neutral-500">
              Pursuit pipeline + Sources Sought drafter ship in Phase 2 Week 7 + Phase 3 Week 11.
            </p>
            {opp.sam_link && (
              <a
                href={opp.sam_link}
                target="_blank"
                rel="noreferrer"
                className="mt-3 block rounded-md border border-neutral-300 px-3 py-2 text-center text-xs font-medium hover:border-neutral-400"
              >
                Open on SAM.gov →
              </a>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-xs uppercase tracking-wider text-neutral-500">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}
