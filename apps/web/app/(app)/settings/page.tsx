import Link from "next/link";
import { apiFetch, type SettingsResponse } from "@/lib/api";
import { deleteFounder } from "@/lib/founders";
import { Badge, Card, LinkButton, PageHeader, Pillar, fmtDate } from "@/components/ui";
import { TermPopover } from "@/components/term-popover";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const data = await apiFetch<SettingsResponse>("/me/settings");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Tenant configuration"
        title="Settings"
        subtitle="Currently read-only — editing UIs ship in a follow-up sprint."
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
          <Row
            label={
              <TermPopover kind="tenant_field" value="uei">UEI</TermPopover>
            }
          >
            {data.tenant.uei ?? <span className="text-muted-foreground">— (pending)</span>}
          </Row>
          <Row
            label={
              <TermPopover kind="tenant_field" value="cage">CAGE</TermPopover>
            }
          >
            {data.tenant.cage_code ?? (
              <span className="text-muted-foreground">— (pending)</span>
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
          <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
            Founders ({data.founders.length})
          </h2>
          <LinkButton href="/settings/founders/new" variant="primary" size="sm">
            + Add founder
          </LinkButton>
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
              {f.profile_linked ? (
                <p
                  className="mt-2 inline-flex items-center gap-1 rounded-sm bg-primary/10 px-1.5 py-px text-[10px] font-medium text-primary"
                  title="Linked to a MacTech Suite user. Title, bio, and NAICS are pulled from their GovCon Ops capability profile when they sign in."
                >
                  Synced from GovCon Ops
                </p>
              ) : null}
              {f.bio ? (
                <p className="mt-2 line-clamp-3 text-xs text-neutral-600">{f.bio}</p>
              ) : null}
              <dl className="mt-3 grid grid-cols-1 gap-y-2 text-xs">
                <Row label="Email">
                  {f.email ?? (
                    <span className="text-muted-foreground">— (not set)</span>
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
              {f.naics.length > 0 ? (
                <div className="mt-3">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    NAICS ({f.naics.length})
                  </p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {f.naics.map((n) => (
                      <span
                        key={n.code}
                        title={n.title}
                        className="inline-flex items-center gap-1 rounded-sm border border-border bg-muted/40 px-1.5 py-px text-[10px]"
                      >
                        <span className="font-mono text-neutral-700">{n.code}</span>
                        <span className="max-w-[10rem] truncate text-muted-foreground">
                          {n.title}
                        </span>
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              <div className="mt-3 flex items-center justify-between border-t border-border pt-2 text-[11px]">
                <span className="text-muted-foreground">@{f.slug}</span>
                <div className="flex items-center gap-3">
                  <Link
                    href={`/settings/founders/${f.id}/edit`}
                    className="text-primary hover:underline"
                  >
                    Edit
                  </Link>
                  <form action={deleteFounder}>
                    <input type="hidden" name="id" value={f.id} />
                    <button
                      type="submit"
                      className="text-muted-foreground hover:text-destructive"
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
        <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
          <TermPopover kind="tenant_field" value="saved_searches">
            Saved searches
          </TermPopover>{" "}
          ({data.saved_searches.length})
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Each saved search drives the founder&rsquo;s morning digest. Threshold +
          cadence + keyword allowlist live here.
        </p>
        <div className="mt-3 space-y-3">
          {data.saved_searches.map((s) => (
            <Card key={s.id}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-base font-semibold text-foreground">{s.name}</p>
                  {s.owner_founder_slug && (
                    <p className="text-xs text-muted-foreground">
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
                <KvList
                  label={
                    <TermPopover kind="naics" value="overview">NAICS</TermPopover>
                  }
                >
                  {s.naics_codes.map((n) => (
                    <Badge key={n} tone="neutral">
                      {n}
                    </Badge>
                  ))}
                </KvList>
                <KvList
                  label={
                    <TermPopover kind="set_aside" value="overview">Set-asides</TermPopover>
                  }
                >
                  {s.set_asides.length === 0 ? (
                    <span className="text-muted-foreground">any</span>
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
                    <span className="text-muted-foreground">none</span>
                  ) : (
                    s.keywords.slice(0, 12).map((kw) => (
                      <Badge key={kw} tone="neutral">
                        {kw}
                      </Badge>
                    ))
                  )}
                  {s.keywords.length > 12 && (
                    <span className="text-muted-foreground">
                      + {s.keywords.length - 12} more
                    </span>
                  )}
                </KvList>
              </div>
              <p className="mt-3 text-[11px] text-muted-foreground">
                Created {fmtDate(s.created_at)}
              </p>
            </Card>
          ))}
        </div>
      </section>

      {/* NAICS matrix */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
          <TermPopover kind="naics" value="matrix">NAICS matrix</TermPopover>{" "}
          ({data.naics.length} codes)
        </h2>
        <div className="mt-3 overflow-hidden rounded-md border border-border bg-card">
          <table className="min-w-full text-sm">
            <thead className="bg-secondary text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-2">Code</th>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Tier</th>
                <th className="px-4 py-2">Owners</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.naics.map((n) => (
                <tr key={n.code}>
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                    {n.code}
                  </td>
                  <td className="px-4 py-2 text-foreground">{n.title}</td>
                  <td className="whitespace-nowrap px-4 py-2">
                    {n.tier === "primary" && (
                      <TermPopover kind="naics" value="tier_primary">
                        <Badge tone="brand">primary</Badge>
                      </TermPopover>
                    )}
                    {n.tier === "secondary" && (
                      <TermPopover kind="naics" value="tier_secondary">
                        <Badge tone="neutral">secondary</Badge>
                      </TermPopover>
                    )}
                    {!n.tier && <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex flex-wrap gap-1">
                      {n.founder_slugs.map((s) => (
                        <span key={s} className="text-[11px] text-muted-foreground">
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

function Row({
  label,
  children
}: {
  label: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
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
  label: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <div className="mt-1 flex flex-wrap gap-1">{children}</div>
    </div>
  );
}
