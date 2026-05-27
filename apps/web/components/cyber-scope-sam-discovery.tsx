import {
  fetchCyberScopeSamSearchStatus,
  runCyberScopeSamSearch,
} from "@/lib/cyber-scope";
import { Badge } from "@/components/ui";

export async function CyberScopeSamDiscovery() {
  const rows = await fetchCyberScopeSamSearchStatus().catch(() => []);

  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">Proactive SAM discovery</p>
        <p className="mt-1 text-xs">
          No cyber-scope saved searches configured. Add{" "}
          <code className="text-xs">cyber_scope_search: true</code> or{" "}
          <code className="text-xs">score_field: cyber_scope_score</code> on a saved
          search.
        </p>
      </div>
    );
  }

  const okCount = rows.filter((r) => r.last_status === "ok").length;
  const latest = rows
    .map((r) => r.last_run_at)
    .filter(Boolean)
    .sort()
    .reverse()[0];

  return (
    <div className="rounded-md border border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-foreground">Proactive SAM discovery</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Daily Beat pulls NAICS + title queries from cyber saved searches, upserts
            opportunities, and enqueues cyber scope scans.
          </p>
        </div>
        <form action={runSamSearch}>
          <button
            type="submit"
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-accent"
          >
            Run SAM search now
          </button>
        </form>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <Badge tone="neutral">{rows.length} SAM jobs</Badge>
        <Badge tone={okCount === rows.length ? "brand" : "amber"}>
          {okCount}/{rows.length} last OK
        </Badge>
        {latest && (
          <span className="text-muted-foreground">Last run {formatWhen(latest)}</span>
        )}
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-muted-foreground">
          Job status
        </summary>
        <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-xs">
          {rows.map((r) => (
            <li key={r.state_key} className="flex flex-wrap gap-2">
              <span className="font-mono text-[10px] text-muted-foreground">
                {shortKey(r.state_key)}
              </span>
              <StatusPill status={r.last_status} />
              {r.last_error && (
                <span className="text-amber-700 dark:text-amber-400 line-clamp-1">
                  {r.last_error}
                </span>
              )}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

async function runSamSearch() {
  "use server";
  await runCyberScopeSamSearch();
}

function shortKey(key: string): string {
  const parts = key.split(":");
  return parts.length >= 2 ? parts.slice(-2).join(":") : key;
}

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function StatusPill({ status }: { status: string | null }) {
  if (status === "ok") {
    return <Badge tone="brand">ok</Badge>;
  }
  if (status === "error") {
    return <Badge tone="amber">error</Badge>;
  }
  return <Badge tone="neutral">{status ?? "never"}</Badge>;
}
