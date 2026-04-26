import Link from "next/link";
import { apiFetch, type SettingsResponse } from "@/lib/api";
import { deleteFounder } from "@/lib/founders";
import { Badge, Card, PageHeader, Pillar, fmtDate } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const data = await apiFetch<SettingsResponse>("/me/settings");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Tenant configuration"
        title="Settings"
        subtitle="Read-only for Phase 2 Week 6. Editing UIs ship in later phases."
      />

      {/* Tenant card */}
      <Card title="Tenant">
        <dl className="grid grid-cols-2 gap-y-2 gap-x-6 text-sm md:grid-cols-3">
          <Row label="Name">{data.tenant.name}</Row>
          <Row label="Slug">
            <span className="font-mono text-xs">{data.tenant.slug}</span>
          </Row>
          <Row label="Plan">
            <Badge tone="neutral">{data.tenant.plan}</Badge>
          </Row>
          <Row label="UEI">
            {data.tenant.uei ?? <span className="text-neutral-400">— (pending)</span>}
          </Row>
          <Row label="CAGE">
            {data.tenant.cage_code ?? (
              <span className="text-neutral-400">— (pending)</span>
            )}
          </Row>
          <Row label="Clerk org">
            <span className="font-mono text-[10px] break-all">
              {data.tenant.clerk_org_id ?? "—"}
            </span>
          </Row>
        </dl>
      </Card>

      {/* Founders */}
      <section id="founders">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
            Founders ({data.founders.length})
          </h2>
          <Link
            href="/settings/founders/new"
            className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
          >
            + Add founder
          </Link>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          {data.founders.map((f) => (
            <Card key={f.slug}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-base font-semibold text-neutral-900">
                    {f.full_name}
                  </p>
                  <p className="text-xs text-neutral-500">{f.title}</p>
                </div>
                <Pillar pillar={f.pillar} />
              </div>
              <dl className="mt-3 grid grid-cols-1 gap-y-2 text-xs">
                <Row label="Email">
                  {f.email ?? (
                    <span className="text-neutral-400">— (not set)</span>
                  )}
                </Row>
                <Row label="Slug">
                  <span className="font-mono">{f.slug}</span>
                </Row>
                <Row label="Digest">
                  {f.digest_enabled ? (
                    <Badge tone="green">enabled</Badge>
                  ) : (
                    <Badge tone="neutral">disabled</Badge>
                  )}
                </Row>
              </dl>
              <div className="mt-3 flex items-center justify-between border-t border-neutral-100 pt-2 text-[11px]">
                <span className="text-neutral-400">@{f.slug}</span>
                <div className="flex items-center gap-3">
                  <Link
                    href={`/settings/founders/${f.id}/edit`}
                    className="text-blue-700 hover:underline"
                  >
                    Edit
                  </Link>
                  <form action={deleteFounder}>
                    <input type="hidden" name="id" value={f.id} />
                    <button
                      type="submit"
                      className="text-neutral-500 hover:text-red-700"
                      title="Permanently remove this founder"
                    >
                      Delete
                    </button>
                  </form>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Saved searches */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
          Saved searches ({data.saved_searches.length})
        </h2>
        <p className="mt-1 text-xs text-neutral-500">
          Each saved search drives the founder's morning digest. Threshold + cadence + keyword
          allowlist live here.
        </p>
        <div className="mt-3 space-y-3">
          {data.saved_searches.map((s) => (
            <Card key={s.id}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-base font-semibold text-neutral-900">{s.name}</p>
                  {s.owner_founder_slug && (
                    <p className="text-xs text-neutral-500">
                      owner @{s.owner_founder_slug}
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge tone="blue">≥ {s.alert_threshold}</Badge>
                  <Badge tone="neutral">{s.alert_cadence}</Badge>
                  {s.alert_channels.map((ch) => (
                    <Badge key={ch} tone="green">
                      {ch}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3 text-xs">
                <KvList label="NAICS">
                  {s.naics_codes.map((n) => (
                    <Badge key={n} tone="neutral">
                      {n}
                    </Badge>
                  ))}
                </KvList>
                <KvList label="Set-asides">
                  {s.set_asides.length === 0 ? (
                    <span className="text-neutral-400">any</span>
                  ) : (
                    s.set_asides.map((sa) => (
                      <Badge key={sa} tone="violet">
                        {sa}
                      </Badge>
                    ))
                  )}
                </KvList>
                <KvList label="Keywords">
                  {s.keywords.length === 0 ? (
                    <span className="text-neutral-400">none</span>
                  ) : (
                    s.keywords.slice(0, 12).map((kw) => (
                      <Badge key={kw} tone="neutral">
                        {kw}
                      </Badge>
                    ))
                  )}
                  {s.keywords.length > 12 && (
                    <span className="text-neutral-500">
                      + {s.keywords.length - 12} more
                    </span>
                  )}
                </KvList>
              </div>
              <p className="mt-3 text-[11px] text-neutral-400">
                Created {fmtDate(s.created_at)}
              </p>
            </Card>
          ))}
        </div>
      </section>

      {/* NAICS matrix */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
          NAICS matrix ({data.naics.length} codes)
        </h2>
        <div className="mt-3 overflow-hidden rounded-md border border-neutral-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-neutral-50 text-left text-[11px] uppercase tracking-wider text-neutral-500">
              <tr>
                <th className="px-4 py-2">Code</th>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Tier</th>
                <th className="px-4 py-2">Owners</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {data.naics.map((n) => (
                <tr key={n.code}>
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                    {n.code}
                  </td>
                  <td className="px-4 py-2 text-neutral-700">{n.title}</td>
                  <td className="whitespace-nowrap px-4 py-2">
                    {n.tier === "primary" && <Badge tone="blue">primary</Badge>}
                    {n.tier === "secondary" && <Badge tone="neutral">secondary</Badge>}
                    {!n.tier && <span className="text-neutral-400">—</span>}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex flex-wrap gap-1">
                      {n.founder_slugs.map((s) => (
                        <span key={s} className="text-[11px] text-neutral-600">
                          @{s}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-neutral-500">
        {label}
      </dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}

function KvList({
  label,
  children
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-neutral-500">
        {label}
      </p>
      <div className="mt-1 flex flex-wrap gap-1">{children}</div>
    </div>
  );
}
