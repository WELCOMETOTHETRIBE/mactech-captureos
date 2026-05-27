"use client";

import { useFormStatus } from "react-dom";
import {
  generateClarificationEmail,
  generateCyberScopeSummary,
  generatePrimeOutreachEmail,
} from "@/lib/cyber-scope";
import type { IntelligenceBundleOut } from "@/lib/api";
import { Button, Card } from "@/components/ui";

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

function CopyBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <pre className="mt-2 whitespace-pre-wrap text-xs text-foreground font-sans">
        {text}
      </pre>
    </div>
  );
}

export function CyberScopeIntelligencePanel({
  analysisId,
  intelligence,
  pursuitModel,
}: {
  analysisId: string;
  intelligence: IntelligenceBundleOut | null | undefined;
  pursuitModel: string;
}) {
  const showPrime =
    pursuitModel === "SUBCONTRACTOR_PURSUE" ||
    pursuitModel === "CYBER_SUPPORT_ONLY";

  return (
    <div className="space-y-4">
      <Card title="AI summary and exports">
        <div className="flex flex-wrap gap-2">
          <form action={generateCyberScopeSummary.bind(null, analysisId)}>
            <ActionBtn label="Generate summary" pendingLabel="Summarizing…" />
          </form>
          <form action={generateClarificationEmail.bind(null, analysisId)}>
            <ActionBtn
              label="CO/COR clarification draft"
              pendingLabel="Drafting…"
            />
          </form>
          {showPrime && (
            <form action={generatePrimeOutreachEmail.bind(null, analysisId)}>
              <ActionBtn label="Prime outreach draft" pendingLabel="Drafting…" />
            </form>
          )}
          <a
            href={`/tools/cyber-scope-parser/${analysisId}/export.pdf`}
            className="inline-flex items-center rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-accent"
          >
            Export PDF
          </a>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Summaries use Claude when configured; otherwise a deterministic template.
          PDF includes summary and clarification draft if generated.
        </p>
      </Card>

      {intelligence?.llm_summary && (
        <Card
          title="Executive summary"
          trailing={
            intelligence.llm_summary_generated_by ? (
              <span className="text-xs text-muted-foreground">
                via {intelligence.llm_summary_generated_by}
              </span>
            ) : null
          }
        >
          <p className="text-sm whitespace-pre-wrap">{intelligence.llm_summary}</p>
        </Card>
      )}

      {intelligence?.clarification_email && (
        <Card title="CO/COR clarification email">
          <CopyBlock
            label="Subject"
            text={intelligence.clarification_email.subject}
          />
          <div className="mt-3">
            <CopyBlock label="Body" text={intelligence.clarification_email.body} />
          </div>
        </Card>
      )}

      {intelligence?.prime_outreach_email && (
        <Card title="Prime subcontractor outreach">
          <CopyBlock
            label="Subject"
            text={intelligence.prime_outreach_email.subject}
          />
          <div className="mt-3">
            <CopyBlock label="Body" text={intelligence.prime_outreach_email.body} />
          </div>
        </Card>
      )}

      {(intelligence?.governance_handoff || intelligence?.pricing_handoff) && (
        <Card title="Ecosystem handoff (stubs)">
          {intelligence.governance_handoff && (
            <p className="text-xs text-muted-foreground mb-2">
              <strong className="text-foreground">GovernanceOS:</strong>{" "}
              {String(intelligence.governance_handoff.message ?? "Readiness checks stub")}
            </p>
          )}
          {intelligence.pricing_handoff && (
            <p className="text-xs text-muted-foreground">
              <strong className="text-foreground">PricingOS:</strong>{" "}
              {String(intelligence.pricing_handoff.message ?? "Labor categories stub")}
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
