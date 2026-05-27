import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchClauseRiskLog } from "@/lib/cyber-scope";
import { Badge, Card, PageHeader } from "@/components/ui";

export const dynamic = "force-dynamic";

const SEVERITY_TONE: Record<string, "red" | "amber" | "neutral" | "violet"> = {
  CRITICAL: "red",
  HIGH: "amber",
  MEDIUM: "violet",
  LOW: "neutral",
};

export default async function ClauseRiskLogPage({
  params,
}: {
  params: Promise<{ logId: string }>;
}) {
  const { logId } = await params;
  let log;
  try {
    log = await fetchClauseRiskLog(logId);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Cyber Scope"
        title={log.title}
        subtitle={`${log.entry_count} risk entries · ${log.status}`}
        trailing={
          <Link
            href={`/tools/cyber-scope-parser/${log.cyber_scope_analysis_id}`}
            className="text-sm text-primary hover:underline"
          >
            Back to analysis
          </Link>
        }
        display
      />

      <p className="text-sm">
        <Link
          href={`/opportunities/${log.opportunity_id}`}
          className="text-primary hover:underline"
        >
          View opportunity
        </Link>
      </p>

      <Card title="Clause risk entries">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-3">Severity</th>
                <th className="py-2 pr-3">Reference</th>
                <th className="py-2 pr-3">Finding</th>
                <th className="py-2">Mitigation</th>
              </tr>
            </thead>
            <tbody>
              {log.entries.map((e) => (
                <tr key={e.id} className="border-b border-border/60 align-top">
                  <td className="py-3 pr-3">
                    <Badge tone={SEVERITY_TONE[e.severity] ?? "neutral"}>
                      {e.severity}
                    </Badge>
                  </td>
                  <td className="py-3 pr-3 font-mono text-xs">{e.reference}</td>
                  <td className="py-3 pr-3">
                    <p>{e.finding}</p>
                    {e.evidence && (
                      <p className="mt-1 text-xs text-muted-foreground line-clamp-3">
                        {e.evidence}
                      </p>
                    )}
                  </td>
                  <td className="py-3 text-muted-foreground">{e.mitigation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
