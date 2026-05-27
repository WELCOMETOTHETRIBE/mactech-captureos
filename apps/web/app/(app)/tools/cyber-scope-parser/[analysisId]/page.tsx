import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchCyberScopeAnalysis, fetchCyberScopeIntelligence } from "@/lib/cyber-scope";
import { CyberScopeIntelligencePanel } from "@/components/cyber-scope-intelligence-panel";
import { Card, PageHeader } from "@/components/ui";
import {
  CyberScopeLikelihoodBadge,
  PursuitModelBadge,
} from "@/components/cyber-scope-likelihood-badge";
import { CyberScopeActionButtons } from "@/components/cyber-scope-action-buttons";

export const dynamic = "force-dynamic";

export default async function CyberScopeAnalysisDetailPage({
  params,
}: {
  params: Promise<{ analysisId: string }>;
}) {
  const { analysisId } = await params;
  let analysis;
  let intelligence;
  try {
    [analysis, intelligence] = await Promise.all([
      fetchCyberScopeAnalysis(analysisId),
      fetchCyberScopeIntelligence(analysisId).catch(() => null),
    ]);
  } catch {
    notFound();
  }

  const queries = (analysis.metadata?.search_queries ?? {}) as Record<
    string,
    string
  >;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Cyber Scope"
        title="Analysis detail"
        subtitle={
          <span>
            Parser {analysis.parser_version} · {analysis.scan_pass} · score{" "}
            {analysis.score}
          </span>
        }
        trailing={
          <Link
            href="/tools/cyber-scope-parser"
            className="text-sm text-primary hover:underline"
          >
            Back to feed
          </Link>
        }
        display
      />

      <div className="flex flex-wrap gap-2">
        <CyberScopeLikelihoodBadge likelihood={analysis.overall_cyber_likelihood} />
        <PursuitModelBadge model={analysis.recommended_pursuit_model} />
        {analysis.ufgs_center_of_gravity && (
          <span className="text-sm text-primary">Center of gravity (25 05 11 + companion)</span>
        )}
      </div>

      {analysis.opportunity_id && (
        <p className="text-sm">
          <Link
            href={`/opportunities/${analysis.opportunity_id}`}
            className="text-primary hover:underline"
          >
            View opportunity
          </Link>
        </p>
      )}

      <CyberScopeActionButtons
        analysisId={analysis.id}
        opportunityId={analysis.opportunity_id}
        downstream={analysis.downstream}
      />

      <CyberScopeIntelligencePanel
        analysisId={analysis.id}
        intelligence={intelligence}
        pursuitModel={analysis.recommended_pursuit_model}
      />

      {analysis.hidden_scope_indicators.length > 0 && (
        <Card title="Hidden scope indicators">
          <ul className="space-y-2 text-sm">
            {analysis.hidden_scope_indicators.map((h, i) => (
              <li key={i} className="border-l-2 border-warning pl-3">
                <strong>{String(h.term ?? "")}</strong>
                <p className="text-muted-foreground">{String(h.surrounding_text ?? "")}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Top signals">
        <ul className="space-y-2 text-sm">
          {analysis.top_signals.map((s, i) => (
            <li key={i}>
              <span className="font-medium">{String(s.term ?? "")}</span>
              <span className="text-muted-foreground"> ({String(s.category ?? "")})</span>
              {s.surrounding_text ? (
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {String(s.surrounding_text)}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      </Card>

      {analysis.missing_but_likely_requirements.length > 0 && (
        <Card title="Missing but likely">
          <ul className="list-disc pl-5 text-sm text-muted-foreground">
            {analysis.missing_but_likely_requirements.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </Card>
      )}

      {Object.keys(queries).length > 0 && (
        <Card title="Search queries (copy to SAM.gov)">
          <dl className="space-y-3 text-xs">
            {Object.entries(queries).map(([key, q]) => (
              <div key={key}>
                <dt className="font-medium uppercase text-muted-foreground">{key}</dt>
                <dd className="mt-1 font-mono text-foreground break-all">{q}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      <Card title="Suggested actions (automated)">
        <ul className="space-y-2 text-sm text-muted-foreground">
          {analysis.suggested_actions.map((a, i) => (
            <li key={i}>
              <strong className="text-foreground">{String(a.title ?? "")}</strong>
              {" — "}
              {String(a.rationale ?? "")}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">
          Use the capture action buttons above to create working artifacts.
        </p>
      </Card>
    </div>
  );
}
