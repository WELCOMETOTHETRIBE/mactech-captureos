import Link from "next/link";
import {
  apiFetch,
  type CapabilityStatementsResponse,
  type PastPerformanceList,
  type TeamingPartnerList
} from "@/lib/api";
import {
  deleteCapabilityStatement,
  deletePastPerformance,
  deleteTeamingPartner,
  toggleTeamingPartnerStatus
} from "@/lib/library-actions";
import {
  Badge,
  Card,
  EmptyState,
  NaicsBadge,
  PageHeader,
  Pillar,
  fmtDate,
  fmtMoney
} from "@/components/ui";

export const dynamic = "force-dynamic";

const ROLE_LABEL: Record<string, string> = {
  prime: "Prime",
  sub: "Sub",
  joint_venture: "Joint venture",
  individual: "Individual"
};

export default async function LibraryPage() {
  const [caps, pastPerf, partners] = await Promise.all([
    apiFetch<CapabilityStatementsResponse>("/capability-statements"),
    apiFetch<PastPerformanceList>("/past-performance"),
    apiFetch<TeamingPartnerList>("/teaming-partners")
  ]);

  const fullyEmbedded = caps.items.filter((i) => i.has_embedding).length;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Capture library"
        title="Library"
        subtitle="Capability statements, past performance, and teaming partners — the catalogue the Phase 3 proposal drafter cites when it generates Sources Sought and capability responses."
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <SummaryStat
          label="Statements"
          value={caps.total}
          hint={`${fullyEmbedded} embedded for vector match`}
        />
        <SummaryStat
          label="Past performance"
          value={pastPerf.total}
          hint="cited in capability responses"
        />
        <SummaryStat
          label="Teaming partners"
          value={partners.total}
          hint={`${partners.active_count} active`}
        />
        <SummaryStat
          label="NAICS coverage"
          value={
            new Set(
              [
                ...caps.items.flatMap((c) => c.related_naics),
                ...pastPerf.items.map((p) => p.naics_code).filter(Boolean)
              ].filter(Boolean) as string[]
            ).size
          }
          hint="distinct codes referenced"
        />
      </div>

      {/* ─── Capability statements ─── */}
      <section id="capability-statements" className="scroll-mt-6 space-y-3">
        <SectionHeader
          title="Capability statements"
          count={caps.total}
          subtitle="Capability clusters MacTech can deliver. The opportunity-scoring engine ranks each new SAM notice against these via pgvector cosine similarity."
          action={
            <div className="flex flex-wrap gap-2">
              <Link
                href="/library/capability-statements/import"
                className="rounded-md border border-brand-300 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-800 hover:border-brand-500"
                title="Drop a capability deck PDF and Claude extracts the fields"
              >
                ⬆ Import PDF
              </Link>
              <Link
                href="/library/capability-statements/new"
                className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
              >
                + Add cluster
              </Link>
            </div>
          }
        />
        {caps.items.length === 0 ? (
          <EmptyState
            title="No capability statements yet."
            body="Capability clusters drive the opportunity-scoring engine. Add at least one before you'll see meaningful capability matches on opportunity detail pages."
            action={
              <div className="flex justify-center gap-2">
                <Link
                  href="/library/capability-statements/import"
                  className="rounded-md border border-brand-300 bg-brand-50 px-3 py-2 text-sm font-medium text-brand-800 hover:border-brand-500"
                >
                  ⬆ Import from PDF
                </Link>
                <Link
                  href="/library/capability-statements/new"
                  className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-800"
                >
                  + Add manually
                </Link>
              </div>
            }
          />
        ) : (
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {caps.items.map((c) => (
              <li key={c.id}>
                <Card>
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-base font-semibold leading-snug text-neutral-900">
                      {c.title}
                    </h3>
                    {c.has_embedding ? (
                      <Badge tone="green">embedded</Badge>
                    ) : (
                      <Badge tone="amber">no embedding</Badge>
                    )}
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-neutral-700">
                    {c.summary}
                  </p>
                  {c.related_naics.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {c.related_naics.map((n) => (
                        <NaicsBadge key={n} code={n} />
                      ))}
                    </div>
                  )}
                  {c.related_founders.length > 0 && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="text-[11px] uppercase tracking-wider text-neutral-500">
                        Owned by
                      </span>
                      {c.related_founders.map((f) => (
                        <span
                          key={f.slug}
                          className="inline-flex items-center gap-1.5 text-xs text-neutral-700"
                        >
                          {f.full_name}
                          <Pillar pillar={f.pillar} />
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="mt-3 flex items-center justify-between border-t border-neutral-100 pt-2 text-[11px]">
                    <span className="text-neutral-400">
                      Updated {fmtDate(c.updated_at)}
                    </span>
                    <div className="flex items-center gap-3">
                      <Link
                        href={`/library/capability-statements/${c.id}/edit`}
                        className="text-blue-700 hover:underline"
                      >
                        Edit
                      </Link>
                      <form action={deleteCapabilityStatement}>
                        <input type="hidden" name="id" value={c.id} />
                        <button
                          type="submit"
                          className="text-neutral-500 hover:text-red-700"
                          title="Permanently delete this capability cluster"
                        >
                          Delete
                        </button>
                      </form>
                    </div>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ─── Past performance ─── */}
      <section id="past-performance" className="scroll-mt-6 space-y-3">
        <SectionHeader
          title="Past performance"
          count={pastPerf.total}
          subtitle="Prior contract narratives the firm cites in capability responses. The Phase 3 proposal drafter will pull from here."
          action={
            <div className="flex flex-wrap gap-2">
              <Link
                href="/library/past-performance/import"
                className="rounded-md border border-brand-300 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-800 hover:border-brand-500"
                title="Drop a prior-engagement PDF and Claude extracts the fields"
              >
                ⬆ Import PDF
              </Link>
              <Link
                href="/library/past-performance/new"
                className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
              >
                + Add record
              </Link>
            </div>
          }
        />
        {pastPerf.items.length === 0 ? (
          <EmptyState
            title="No past-performance records yet."
            body="Add the prior engagements you'd cite in a capability response. Each row becomes a citation the proposal drafter can pull from."
            action={
              <div className="flex justify-center gap-2">
                <Link
                  href="/library/past-performance/import"
                  className="rounded-md border border-brand-300 bg-brand-50 px-3 py-2 text-sm font-medium text-brand-800 hover:border-brand-500"
                >
                  ⬆ Import from PDF
                </Link>
                <Link
                  href="/library/past-performance/new"
                  className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-800"
                >
                  + Add manually
                </Link>
              </div>
            }
          />
        ) : (
          <ul className="space-y-3">
            {pastPerf.items.map((p) => (
              <li key={p.id}>
                <Card>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold leading-snug text-neutral-900">
                        {p.title}
                      </h3>
                      <p className="mt-1 text-xs text-neutral-500">
                        {[
                          p.customer_agency,
                          p.customer_office,
                          p.contract_number && `#${p.contract_number}`
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <Badge tone="blue">{ROLE_LABEL[p.role] ?? p.role}</Badge>
                      {p.contract_value != null && (
                        <span className="tabular-nums text-sm font-semibold text-neutral-800">
                          {fmtMoney(p.contract_value)}
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-neutral-700">
                    {p.summary}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-neutral-500">
                    {p.naics_code && <NaicsBadge code={p.naics_code} />}
                    {(p.period_start || p.period_end) && (
                      <span>
                        {fmtDate(p.period_start)} – {fmtDate(p.period_end)}
                      </span>
                    )}
                    {p.related_founder_slugs.length > 0 && (
                      <span>
                        Owners:{" "}
                        {p.related_founder_slugs.map((s) => `@${s}`).join(", ")}
                      </span>
                    )}
                    {p.keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {p.keywords.slice(0, 8).map((k) => (
                          <Badge key={k} tone="neutral">
                            {k}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="mt-3 flex items-center justify-between border-t border-neutral-100 pt-2 text-[11px]">
                    <span className="text-neutral-400">
                      Updated {fmtDate(p.updated_at)}
                    </span>
                    <div className="flex items-center gap-3">
                      <Link
                        href={`/library/past-performance/${p.id}/edit`}
                        className="text-blue-700 hover:underline"
                      >
                        Edit
                      </Link>
                      <form action={deletePastPerformance}>
                        <input type="hidden" name="id" value={p.id} />
                        <button
                          type="submit"
                          className="text-neutral-500 hover:text-red-700"
                        >
                          Delete
                        </button>
                      </form>
                    </div>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ─── Teaming partners ─── */}
      <section id="teaming-partners" className="scroll-mt-6 space-y-3">
        <SectionHeader
          title="Teaming partners"
          count={partners.total}
          subtitle="Relationship roster for multi-vendor pursuits. Active partners surface in the proposal drafter's teaming suggestions."
          action={
            <Link
              href="/library/teaming-partners/new"
              className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
            >
              + Add partner
            </Link>
          }
        />
        {partners.items.length === 0 ? (
          <EmptyState
            title="No teaming partners yet."
            body="Add the primes/subs you'd team with on multi-vendor pursuits. Capabilities + NAICS codes drive automatic suggestions on opportunity detail pages."
            action={
              <Link
                href="/library/teaming-partners/new"
                className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-800"
              >
                + Add the first partner
              </Link>
            }
          />
        ) : (
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {partners.items.map((p) => (
              <li key={p.id}>
                <Card>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold leading-snug text-neutral-900">
                        {p.name}
                      </h3>
                      <p className="mt-1 text-xs text-neutral-500">
                        {[p.uei && `UEI ${p.uei}`, p.cage_code && `CAGE ${p.cage_code}`]
                          .filter(Boolean)
                          .join(" · ") || "—"}
                      </p>
                    </div>
                    <Badge tone={p.status === "active" ? "green" : "neutral"}>
                      {p.status}
                    </Badge>
                  </div>
                  {p.capabilities.length > 0 && (
                    <div className="mt-3">
                      <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                        Capabilities
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {p.capabilities.map((c) => (
                          <Badge key={c} tone="blue">
                            {c}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {p.naics_codes.length > 0 && (
                    <div className="mt-3">
                      <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                        NAICS
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {p.naics_codes.map((n) => (
                          <NaicsBadge key={n} code={n} />
                        ))}
                      </div>
                    </div>
                  )}
                  {p.set_aside_certifications.length > 0 && (
                    <div className="mt-3">
                      <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                        Set-aside certs
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {p.set_aside_certifications.map((c) => (
                          <Badge key={c} tone="violet">
                            {c}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {(p.contact_name || p.contact_email) && (
                    <div className="mt-3 text-xs text-neutral-700">
                      <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                        Contact
                      </p>
                      <p className="mt-0.5">
                        {p.contact_name}
                        {p.contact_email && (
                          <>
                            {p.contact_name && " · "}
                            <a
                              href={`mailto:${p.contact_email}`}
                              className="text-blue-700 hover:underline"
                            >
                              {p.contact_email}
                            </a>
                          </>
                        )}
                      </p>
                    </div>
                  )}
                  {p.notes && (
                    <p className="mt-3 whitespace-pre-wrap text-xs leading-relaxed text-neutral-600">
                      {p.notes}
                    </p>
                  )}
                  <div className="mt-3 flex items-center justify-between border-t border-neutral-100 pt-2 text-[11px]">
                    <span className="text-neutral-400">
                      Updated {fmtDate(p.updated_at)}
                    </span>
                    <div className="flex items-center gap-3">
                      <Link
                        href={`/library/teaming-partners/${p.id}/edit`}
                        className="text-blue-700 hover:underline"
                      >
                        Edit
                      </Link>
                      <form action={toggleTeamingPartnerStatus}>
                        <input type="hidden" name="id" value={p.id} />
                        <input
                          type="hidden"
                          name="next_status"
                          value={p.status === "active" ? "inactive" : "active"}
                        />
                        <button
                          type="submit"
                          className="text-neutral-500 hover:text-neutral-800"
                        >
                          {p.status === "active" ? "Archive" : "Reactivate"}
                        </button>
                      </form>
                      <form action={deleteTeamingPartner}>
                        <input type="hidden" name="id" value={p.id} />
                        <button
                          type="submit"
                          className="text-neutral-500 hover:text-red-700"
                        >
                          Delete
                        </button>
                      </form>
                    </div>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function SectionHeader({
  title,
  count,
  subtitle,
  action
}: {
  title: string;
  count: number;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3 border-b border-neutral-200 pb-2">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
          {title}{" "}
          <span className="text-neutral-400 font-normal normal-case">({count})</span>
        </h2>
        {subtitle && (
          <p className="mt-1 max-w-2xl text-xs text-neutral-500">{subtitle}</p>
        )}
      </div>
      {action}
    </header>
  );
}

function SummaryStat({
  label,
  value,
  hint
}: {
  label: string;
  value: number;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-neutral-200 bg-white p-4">
      <p className="text-[11px] uppercase tracking-wider text-neutral-500">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-[11px] text-neutral-500">{hint}</p>}
    </div>
  );
}
