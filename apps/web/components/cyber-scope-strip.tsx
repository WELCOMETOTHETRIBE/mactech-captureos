import Link from "next/link";
import { Badge } from "@/components/ui";
import {
  CyberScopeLikelihoodBadge,
  PursuitModelBadge,
} from "@/components/cyber-scope-likelihood-badge";
import type { CyberScopeBlock, ScoreBlock } from "@/lib/api";
import { CyberScopeRescanButton } from "@/components/cyber-scope-rescan-button";
import { CyberScopeActionButtons } from "@/components/cyber-scope-action-buttons";

/**
 * Cyber Scope strip on opportunity detail — shows when cyber_scope_score
 * is set and likelihood is at least MEDIUM.
 */
export function CyberScopeStrip({
  opportunityId,
  score,
}: {
  opportunityId: string;
  score: ScoreBlock | null;
}) {
  const cs = score?.cyber_scope;
  if (!cs) return null;
  if (cs.likelihood === "NONE" || cs.likelihood === "LOW") return null;

  const hasUfgs = cs.top_ufgs_sections.length > 0;
  const hasSignals = cs.top_signals.length > 0;

  return (
    <section
      className="rounded-md border border-border border-l-[3px] border-l-primary bg-card p-5"
      aria-label="Cyber scope analysis"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[11px] font-medium uppercase tracking-wider text-primary">
          Cyber scope (FRCS / OT / UFGS)
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <CyberScopeLikelihoodBadge likelihood={cs.likelihood} />
          <PursuitModelBadge model={cs.pursuit_model} />
          {cs.ufgs_center_of_gravity && (
            <Badge tone="brand">Center of gravity</Badge>
          )}
          {cs.attachments_pending && (
            <Badge tone="amber">Attachments pending</Badge>
          )}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="min-w-0 space-y-2">
          <p className="text-sm text-muted-foreground">
            Score {cs.score} · scan {cs.scan_pass.replace(/_/g, " ")}
            {cs.ufgs_tier_1_hit ? " · Tier 1 UFGS detected" : ""}
          </p>
          {hasUfgs && (
            <div className="flex flex-wrap gap-1">
              {cs.top_ufgs_sections.map((u) => (
                <Badge key={u} tone="neutral">
                  {u}
                </Badge>
              ))}
            </div>
          )}
          {hasSignals && (
            <p className="text-xs text-muted-foreground line-clamp-3">
              {String(cs.top_signals[0]?.term ?? "")}
              {cs.top_signals[0]?.surrounding_text
                ? ` — ${String(cs.top_signals[0].surrounding_text).slice(0, 160)}`
                : ""}
            </p>
          )}
        </div>
        <div className="flex flex-col items-start gap-2 lg:items-end">
          {cs.analysis_url && (
            <Link
              href={cs.analysis_url}
              className="text-sm font-medium text-primary hover:underline"
            >
              Full cyber scope analysis
            </Link>
          )}
          <Link
            href="/tools/cyber-scope-parser"
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Open cyber scope feed
          </Link>
          <CyberScopeRescanButton opportunityId={opportunityId} />
        </div>
      </div>
      {cs.analysis_id && (
        <div className="mt-4 border-t border-border pt-4">
          <CyberScopeActionButtons
            analysisId={cs.analysis_id}
            opportunityId={opportunityId}
            compact
          />
        </div>
      )}
    </section>
  );
}
