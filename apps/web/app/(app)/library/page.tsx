import { apiFetch, type CapabilityStatementsResponse } from "@/lib/api";
import {
  Badge,
  Card,
  EmptyState,
  PageHeader,
  Pillar,
  fmtDate
} from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function LibraryPage() {
  const data = await apiFetch<CapabilityStatementsResponse>("/capability-statements");
  const fullyEmbedded = data.items.filter((i) => i.has_embedding).length;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Capture library"
        title="Capability statements"
        subtitle={`MacTech's ${data.total} capability statements — the basis for the pgvector capability-match scoring on every opportunity.`}
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <SummaryStat label="Statements" value={data.total} />
        <SummaryStat
          label="Embedded"
          value={fullyEmbedded}
          hint="for similarity matching"
        />
        <SummaryStat
          label="Past performance"
          value={0}
          hint="Phase 2 Week 8"
        />
        <SummaryStat
          label="Teaming partners"
          value={0}
          hint="Phase 2 Week 8"
        />
      </div>

      {data.items.length === 0 ? (
        <EmptyState
          title="No capability statements seeded."
          body="Run the seed script — config/mactech_tenant_defaults.yml controls this list."
        />
      ) : (
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {data.items.map((c) => (
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
                      <Badge key={n} tone="neutral">
                        NAICS {n}
                      </Badge>
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
                <p className="mt-3 text-[11px] text-neutral-400">
                  Updated {fmtDate(c.updated_at)}
                </p>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
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
