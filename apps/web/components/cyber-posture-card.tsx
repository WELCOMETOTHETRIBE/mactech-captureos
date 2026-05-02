import { Badge, Card, ExplainLink, Term, fmtDate } from "@/components/ui";
import type { CyberSummaryOut } from "@/lib/api";

export function CyberPostureCard({ summary }: { summary: CyberSummaryOut }) {
  const hasAnyCyberAsk =
    summary.clauses_identified.length > 0 ||
    summary.cmmc_level_required != null ||
    summary.handles_cui ||
    summary.handles_fci ||
    summary.handles_itar;

  return (
    <Card title="Cyber posture vs. solicitation">
      <SufficiencyBanner summary={summary} hasAsk={hasAnyCyberAsk} />

      <dl className="mt-4 grid grid-cols-1 gap-3 text-sm">
        <SprsRow summary={summary} />
        {summary.cmmc_level_required && (
          <Row label="CMMC required">
            <ExplainLink slug={`cmmc:${summary.cmmc_level_required}`}>
              <Badge tone="blue">{summary.cmmc_level_required}</Badge>
            </ExplainLink>
          </Row>
        )}
        {summary.clauses_identified.length > 0 && (
          <Row label="Clauses cited">
            <div className="flex flex-wrap justify-end gap-1.5">
              {summary.clauses_identified.map((c) => (
                <ExplainLink key={c} slug={`clause:${c}`}>
                  <Badge tone="neutral">{c}</Badge>
                </ExplainLink>
              ))}
            </div>
          </Row>
        )}
        {(summary.handles_cui ||
          summary.handles_fci ||
          summary.handles_itar) && (
          <Row label="Data sensitivity">
            <div className="flex flex-wrap justify-end gap-1.5">
              {summary.handles_cui && (
                <ExplainLink slug="cui:CUI">
                  <Badge tone="amber">CUI</Badge>
                </ExplainLink>
              )}
              {summary.handles_fci && (
                <ExplainLink slug="fci:FCI">
                  <Badge tone="neutral">FCI</Badge>
                </ExplainLink>
              )}
              {summary.handles_itar && (
                <ExplainLink slug="itar:ITAR">
                  <Badge tone="red">ITAR</Badge>
                </ExplainLink>
              )}
            </div>
          </Row>
        )}
      </dl>

      {!hasAnyCyberAsk && (
        <p className="mt-4 text-sm text-neutral-600">
          No cyber clauses or CMMC requirements detected in the description.
          File-level extraction (V2) may surface more once attached PDFs are
          ingested.
        </p>
      )}

      {summary.posture.sprs_source_url && (
        <p className="mt-4 text-[11px] text-neutral-500">
          SPRS posture synced from{" "}
          <a
            href={summary.posture.sprs_source_url}
            target="_blank"
            rel="noreferrer"
            className="text-brand-700 hover:underline"
          >
            Codex
          </a>
          {summary.posture.sprs_synced_at &&
            ` · ${fmtDate(summary.posture.sprs_synced_at)}`}
        </p>
      )}
    </Card>
  );
}

function SufficiencyBanner({
  summary,
  hasAsk,
}: {
  summary: CyberSummaryOut;
  hasAsk: boolean;
}) {
  if (!hasAsk) return null;

  if (summary.sufficiency === "sufficient") {
    return (
      <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3">
        <p className="flex items-center gap-2 text-sm font-medium text-emerald-900">
          <span aria-hidden>✓</span> Cyber posture appears sufficient for this
          opportunity.
        </p>
        {summary.sufficiency_notes && (
          <p className="mt-1 text-[11px] text-emerald-800">
            {summary.sufficiency_notes}
          </p>
        )}
      </div>
    );
  }

  if (summary.sufficiency === "gap") {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-3">
        <p className="flex items-center gap-2 text-sm font-medium text-red-900">
          <span aria-hidden>!</span> Cyber posture gap — remediate before
          bidding.
        </p>
        {summary.sufficiency_notes && (
          <p className="mt-1 text-[11px] text-red-800">
            {summary.sufficiency_notes}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
      <p className="flex items-center gap-2 text-sm font-medium text-amber-900">
        <span aria-hidden>?</span> Sufficiency unknown — confirm posture
        directly.
      </p>
      {summary.sufficiency_notes && (
        <p className="mt-1 text-[11px] text-amber-800">
          {summary.sufficiency_notes}
        </p>
      )}
    </div>
  );
}

function SprsRow({ summary }: { summary: CyberSummaryOut }) {
  const score = summary.posture.sprs_score;
  const max = summary.posture.sprs_max;
  if (score == null) {
    return (
      <Row label={<Term kind="sprs" value="SPRS">SPRS score</Term>}>
        <span className="text-neutral-500">
          Not on file. Sync from Codex.
        </span>
      </Row>
    );
  }
  const tone = score >= 80 ? "green" : score >= 0 ? "amber" : "red";
  return (
    <Row label={<Term kind="sprs" value="SPRS">SPRS score</Term>}>
      <span className="inline-flex items-baseline gap-1">
        <Badge tone={tone}>
          <span className="tabular-nums font-semibold">{score}</span>
          <span className="ml-1 text-[10px] opacity-70">/ {max}</span>
        </Badge>
        {summary.posture.sprs_assessment_date && (
          <span className="text-[11px] text-neutral-500">
            assessed {fmtDate(summary.posture.sprs_assessment_date)}
          </span>
        )}
      </span>
    </Row>
  );
}

function Row({
  label,
  children,
}: {
  label: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-[11px] uppercase tracking-wider text-neutral-500">
        {label}
      </dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}
