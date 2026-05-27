"use client";

import { useFormStatus } from "react-dom";
import Link from "next/link";
import {
  addCyberScopeToPipeline,
  createBidNoBidReviewFromAnalysis,
  createClauseRiskLogFromAnalysis,
  createProposalOutlineFromAnalysis,
} from "@/lib/cyber-scope";
import type { CyberScopeDownstreamOut } from "@/lib/api";
import { Button } from "@/components/ui";

function ActionBtn({
  label,
  pendingLabel,
}: {
  label: string;
  pendingLabel: string;
}) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" variant="secondary" disabled={pending} className="text-xs">
      {pending ? pendingLabel : label}
    </Button>
  );
}

export function CyberScopeActionButtons({
  analysisId,
  opportunityId,
  downstream,
  compact = false,
}: {
  analysisId: string;
  opportunityId: string | null;
  downstream?: CyberScopeDownstreamOut | null;
  compact?: boolean;
}) {
  if (!opportunityId) {
    return (
      <p className="text-xs text-muted-foreground">
        Link to a SAM opportunity to run capture actions.
      </p>
    );
  }

  const d: CyberScopeDownstreamOut = downstream ?? {
    clause_risk_log_id: null,
    bid_no_bid_review_id: null,
    proposal_outline_id: null,
    pursuit_id: null,
  };

  return (
    <div
      className={
        compact
          ? "flex flex-wrap gap-2"
          : "flex flex-col gap-3 rounded-md border border-border bg-card p-4"
      }
    >
      {!compact && (
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Capture actions
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {d.clause_risk_log_id ? (
          <Link
            href={`/tools/cyber-scope-parser/clause-risk/${d.clause_risk_log_id}`}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-accent"
          >
            Clause risk log
          </Link>
        ) : (
          <form action={createClauseRiskLogFromAnalysis.bind(null, analysisId)}>
            <ActionBtn label="Clause risk log" pendingLabel="Drafting…" />
          </form>
        )}

        {d.bid_no_bid_review_id ? (
          <Link
            href={`/tools/cyber-scope-parser/bid-review/${d.bid_no_bid_review_id}`}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-accent"
          >
            Bid/no-bid review
          </Link>
        ) : (
          <form action={createBidNoBidReviewFromAnalysis.bind(null, analysisId)}>
            <ActionBtn label="Bid/no-bid prefill" pendingLabel="Prefilling…" />
          </form>
        )}

        {d.proposal_outline_id ? (
          <Link
            href={`/tools/cyber-scope-parser/outline/${d.proposal_outline_id}`}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-accent"
          >
            Proposal outline
          </Link>
        ) : (
          <form action={createProposalOutlineFromAnalysis.bind(null, analysisId)}>
            <ActionBtn label="Proposal outline" pendingLabel="Building…" />
          </form>
        )}

        {d.pursuit_id ? (
          <Link
            href={`/pursuits/${d.pursuit_id}`}
            className="rounded-md border border-primary px-3 py-1.5 text-xs font-medium text-primary hover:bg-accent"
          >
            In pipeline
          </Link>
        ) : (
          <form action={addCyberScopeToPipeline.bind(null, analysisId)}>
            <ActionBtn label="Add to pipeline" pendingLabel="Adding…" />
          </form>
        )}
      </div>
    </div>
  );
}
