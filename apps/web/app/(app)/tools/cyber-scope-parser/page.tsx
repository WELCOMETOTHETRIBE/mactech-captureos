import type { ReactNode } from "react";
import Link from "next/link";
import {
  fetchCyberScopeFeed,
  analyzePastedCyberScope,
} from "@/lib/cyber-scope";
import {
  Badge,
  Card,
  EmptyState,
  PageHeader,
} from "@/components/ui";
import {
  CyberScopeLikelihoodBadge,
  PursuitModelBadge,
} from "@/components/cyber-scope-likelihood-badge";
import { CyberScopeOffplatformForm } from "@/components/cyber-scope-offplatform-form";
import { CyberScopeActionButtons } from "@/components/cyber-scope-action-buttons";
import { CyberScopeSamDiscovery } from "@/components/cyber-scope-sam-discovery";

export const dynamic = "force-dynamic";

export default async function CyberScopeParserPage({
  searchParams,
}: {
  searchParams?: Promise<{
    view?: string;
    analysis?: string;
    filter?: string;
  }>;
}) {
  const sp = (await searchParams) ?? {};
  const filter = sp.filter ?? "high";
  const likelihoodParam =
    filter === "critical"
      ? "CRITICAL"
      : filter === "high"
        ? "HIGH,CRITICAL"
        : filter === "cog"
          ? undefined
          : "MEDIUM,HIGH,CRITICAL";

  const feed = await fetchCyberScopeFeed({
    likelihood: likelihoodParam,
    center_of_gravity: filter === "cog" ? true : undefined,
    ufgs_tier_1: filter === "tier1" ? true : undefined,
    min_score: filter === "all" ? 15 : filter === "cog" ? 40 : 65,
  }).catch(() => ({ total: 0, items: [] }));

  const criticalCount = feed.items.filter(
    (i) => i.overall_cyber_likelihood === "CRITICAL"
  ).length;
  const cogCount = feed.items.filter((i) => i.ufgs_center_of_gravity).length;

  async function offplatformAction(formData: FormData) {
    "use server";
    await analyzePastedCyberScope(formData);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Tools"
        title="Cyber Scope Parser"
        subtitle="Automatically detects hidden FRCS, OT, ICS, RMF, ATO, UFC, UFGS, and CMMC requirements from SAM-ingested solicitations and attachments. UFGS 25 05 11 is the center of gravity."
        display
      />

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <a
          href={`/tools/cyber-scope-parser/export.csv?${exportCsvQuery(filter)}`}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-accent"
        >
          Export CSV
        </a>
        <FilterLink href="?filter=high" active={filter === "high"}>
          High / Critical
        </FilterLink>
        <FilterLink href="?filter=critical" active={filter === "critical"}>
          Critical only
        </FilterLink>
        <FilterLink href="?filter=cog" active={filter === "cog"}>
          Center of gravity
        </FilterLink>
        <FilterLink href="?filter=tier1" active={filter === "tier1"}>
          Tier 1 UFGS
        </FilterLink>
        <FilterLink href="?filter=all" active={filter === "all"}>
          All scored
        </FilterLink>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Kpi label="Feed matches" value={String(feed.total)} />
        <Kpi label="Critical in view" value={String(criticalCount)} />
        <Kpi label="25 05 11 + companion" value={String(cogCount)} />
      </div>

      <CyberScopeSamDiscovery />

      <Card title="Cyber scope feed (auto-discovered)">
        {feed.items.length === 0 ? (
          <EmptyState
            title="No analyses yet"
            body="Runs automatically after SAM ingest and attachment fetch. Check back after the next ingest cycle, or use off-platform analysis below."
          />
        ) : (
          <ul className="divide-y divide-border">
            {feed.items.map((item) => (
              <li key={item.id} className="py-4 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    {item.opportunity_url ? (
                      <Link
                        href={item.opportunity_url}
                        className="font-medium text-foreground hover:text-primary"
                      >
                        {item.title ?? "Untitled opportunity"}
                      </Link>
                    ) : (
                      <span className="font-medium">{item.title ?? "Off-platform"}</span>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground">
                      {[item.agency, item.solicitation_number, item.scan_pass]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {item.ufgs_tier_1_hit && (
                        <Badge tone="violet">T1 · 25 05 11</Badge>
                      )}
                      {item.ufgs_center_of_gravity && (
                        <Badge tone="brand">CoG</Badge>
                      )}
                      {item.attachments_pending && (
                        <Badge tone="amber">Attachments pending</Badge>
                      )}
                      {item.top_ufgs_sections.slice(0, 4).map((u) => (
                        <Badge key={u} tone="neutral">
                          {u}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <CyberScopeLikelihoodBadge
                      likelihood={item.overall_cyber_likelihood}
                    />
                    <PursuitModelBadge model={item.recommended_pursuit_model} />
                    <span className="text-xs text-muted-foreground">
                      Score {item.score}
                    </span>
                    <Link
                      href={`/tools/cyber-scope-parser/${item.id}`}
                      className="text-xs font-medium text-primary hover:underline"
                    >
                      View analysis
                    </Link>
                  </div>
                </div>
                {item.opportunity_id && (
                  <div className="mt-3">
                    <CyberScopeActionButtons
                      analysisId={item.id}
                      opportunityId={item.opportunity_id}
                      compact
                    />
                  </div>
                )}
                {item.top_signals[0] && (
                  <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
                    {item.top_signals[0].term}
                    {item.top_signals[0].surrounding_text
                      ? ` — ${String(item.top_signals[0].surrounding_text).slice(0, 120)}`
                      : ""}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <details className="rounded-md border border-border bg-card p-4">
        <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
          Off-platform analysis (supplemental)
        </summary>
        <p className="mt-2 text-xs text-muted-foreground">
          For prime bid packages or emails not on SAM. Primary discovery is API-driven.
        </p>
        <div className="mt-4">
          <CyberScopeOffplatformForm action={offplatformAction} />
        </div>
      </details>
    </div>
  );
}

function exportCsvQuery(filter: string): string {
  const q = new URLSearchParams();
  if (filter === "critical") {
    q.set("likelihood", "CRITICAL");
    q.set("min_score", "65");
  } else if (filter === "high") {
    q.set("likelihood", "HIGH,CRITICAL");
    q.set("min_score", "65");
  } else if (filter === "all") {
    q.set("min_score", "15");
  } else if (filter === "cog") {
    q.set("min_score", "40");
  } else {
    q.set("min_score", "65");
  }
  return q.toString();
}

function FilterLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={`/tools/cyber-scope-parser${href}`}
      className={
        active
          ? "rounded-md bg-primary/10 px-3 py-1 font-medium text-primary"
          : "rounded-md px-3 py-1 text-muted-foreground hover:bg-accent"
      }
    >
      {children}
    </Link>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}
