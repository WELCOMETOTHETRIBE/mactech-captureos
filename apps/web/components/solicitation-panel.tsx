import { Badge, Card, Term, fmtDate } from "@/components/ui";
import {
  generateSolicitationExtraction,
  deleteSolicitationExtraction,
} from "@/lib/solicitation";
import type {
  ComplianceMatrixOut,
  EvaluationOut,
  RequirementCategory,
  RequirementsMatrixOut,
  SolicitationExtractionOut,
} from "@/lib/api";

type Props = {
  opportunityId: string;
  hasDescription: boolean;
  extraction: SolicitationExtractionOut | null;
  compliance: ComplianceMatrixOut | null;
  requirements: RequirementsMatrixOut | null;
  evaluation: EvaluationOut | null;
};

export function SolicitationPanel({
  opportunityId,
  hasDescription,
  extraction,
  compliance,
  requirements,
  evaluation,
}: Props) {
  const generateAction = generateSolicitationExtraction.bind(null, opportunityId);
  const totalItems =
    (compliance?.items.length ?? 0) +
    (requirements?.items.length ?? 0) +
    (evaluation?.pass_fail_items.length ?? 0) +
    (evaluation?.scored_factors.length ?? 0);

  return (
    <Card>
      <header className="flex flex-wrap items-baseline justify-between gap-3 border-b border-neutral-100 pb-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">
            Solicitation decoder
          </p>
          <p className="mt-1 text-sm text-neutral-600">
            Compliance matrix (<Term kind="section" value="L">Section L</Term>) +
            requirements matrix (<Term kind="section" value="SOW">SOW</Term>/
            <Term kind="section" value="PWS">PWS</Term>) extracted by Claude.
            Feeds the Capture Package handoff to ProposalOS.
          </p>
        </div>
        {extraction ? (
          <div className="flex items-center gap-2">
            <form action={generateAction}>
              <button
                type="submit"
                className="rounded-md px-2 py-1 text-[11px] text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800"
                title="Re-run Claude on the current description"
              >
                ↻ Regenerate
              </button>
            </form>
            <form action={deleteSolicitationExtraction}>
              <input type="hidden" name="opportunity_id" value={opportunityId} />
              <button
                type="submit"
                className="rounded-md border border-neutral-200 px-2 py-1 text-[11px] text-neutral-500 hover:border-red-300 hover:text-red-700"
                title="Throw out the cached matrices"
              >
                Delete
              </button>
            </form>
          </div>
        ) : null}
      </header>

      {!extraction ? (
        <SolicitationEmpty
          generateAction={generateAction}
          hasDescription={hasDescription}
        />
      ) : totalItems === 0 ? (
        <ExtractedButEmpty extraction={extraction} />
      ) : (
        <div className="space-y-6 pt-4">
          {extraction.status === "stale" && (
            <StaleExtractionBanner generateAction={generateAction} />
          )}
          <ExtractionMeta extraction={extraction} />
          <ComplianceMatrixTable compliance={compliance} />
          <RequirementsMatrixTable requirements={requirements} />
          <EvaluationTables evaluation={evaluation} />
        </div>
      )}
    </Card>
  );
}

function StaleExtractionBanner({
  generateAction,
}: {
  generateAction: () => Promise<void>;
}) {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-amber-900">
            Matrices are stale — opportunity was amended after the last extraction.
          </p>
          <p className="mt-1 text-[11px] text-amber-800">
            Re-run extraction to pull updated{" "}
            <Term kind="section" value="L">Section L</Term> /{" "}
            <Term kind="section" value="SOW">SOW</Term> /{" "}
            <Term kind="section" value="M">Section M</Term> from the latest
            SAM payload.
          </p>
        </div>
        <form action={generateAction}>
          <button
            type="submit"
            className="rounded-md border border-amber-700 bg-amber-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-800"
          >
            Re-extract now →
          </button>
        </form>
      </div>
    </div>
  );
}

function SolicitationEmpty({
  generateAction,
  hasDescription,
}: {
  generateAction: () => Promise<void>;
  hasDescription: boolean;
}) {
  if (!hasDescription) {
    return (
      <div className="pt-4 text-sm text-neutral-600">
        Description text isn&rsquo;t on file yet — the SAM description fetcher
        runs every 30 minutes. Once the text lands, generate the matrices to
        populate this panel.
      </div>
    );
  }
  return (
    <div className="flex flex-col items-start gap-3 pt-4">
      <p className="text-sm text-neutral-600">
        Not generated yet. Claude will read the SAM description and produce a
        compliance matrix (every &ldquo;shall&rdquo; in{" "}
        <Term kind="section" value="L">Section L</Term>) and a requirements
        matrix (<Term kind="section" value="SOW">SOW</Term> /{" "}
        <Term kind="section" value="PWS">PWS</Term> obligations). Typical run
        takes 30–60s.
      </p>
      <form action={generateAction}>
        <button
          type="submit"
          className="rounded-md border border-brand-700 bg-brand-700 px-3 py-2 text-sm font-medium text-white hover:bg-brand-800"
        >
          Generate compliance + requirements matrices →
        </button>
      </form>
      <p className="text-[11px] text-neutral-500">
        Honest scope: when the real Section L lives in attached PDFs, the
        matrices will be partial. Re-run after file ingest is built (V2).
      </p>
    </div>
  );
}

function ExtractedButEmpty({
  extraction,
}: {
  extraction: SolicitationExtractionOut;
}) {
  return (
    <div className="pt-4 text-sm">
      <Badge tone="amber">Extraction complete · 0 items</Badge>
      <p className="mt-3 text-neutral-700">
        Claude ran but found no extractable Section L instructions or SOW
        obligations in the current description. Most likely cause: the real
        solicitation lives in attached PDFs that CaptureOS doesn&rsquo;t yet
        ingest.
      </p>
      <p className="mt-2 text-[11px] text-neutral-500">
        Last attempt {fmtDate(extraction.updated_at)} ·{" "}
        {extraction.description_chars?.toLocaleString() ?? "?"} chars analyzed ·{" "}
        {extraction.input_tokens?.toLocaleString() ?? "?"} in /{" "}
        {extraction.output_tokens?.toLocaleString() ?? "?"} out tokens
      </p>
    </div>
  );
}

function ExtractionMeta({
  extraction,
}: {
  extraction: SolicitationExtractionOut;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-neutral-500">
      <Badge tone="green">{extraction.compliance_count} compliance items</Badge>
      <Badge tone="blue">{extraction.requirements_count} requirement items</Badge>
      <Badge tone="violet">{extraction.evaluation_count} evaluation items</Badge>
      <span>
        Generated by {extraction.model ?? "Claude"} on{" "}
        {fmtDate(extraction.updated_at)} from{" "}
        {extraction.description_chars?.toLocaleString() ?? "?"} chars ·{" "}
        {extraction.input_tokens?.toLocaleString() ?? "?"} in /{" "}
        {extraction.output_tokens?.toLocaleString() ?? "?"} out tokens
      </span>
    </div>
  );
}

function ComplianceMatrixTable({
  compliance,
}: {
  compliance: ComplianceMatrixOut | null;
}) {
  if (!compliance || compliance.items.length === 0) {
    return null;
  }
  return (
    <section>
      <header className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-neutral-900">
          Compliance matrix · <Term kind="section" value="L">Section L</Term> instructions
        </h3>
        <span className="text-[11px] text-neutral-500">
          {compliance.items.length}{" "}
          {compliance.items.length === 1 ? "item" : "items"}
        </span>
      </header>
      <div className="overflow-hidden rounded-md border border-neutral-200">
        <table className="w-full table-fixed text-sm">
          <colgroup>
            <col className="w-16" />
            <col />
            <col className="w-44" />
            <col className="w-20" />
          </colgroup>
          <thead className="bg-neutral-50 text-[11px] uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-3 py-2 text-left font-medium">ID</th>
              <th className="px-3 py-2 text-left font-medium">Statement</th>
              <th className="px-3 py-2 text-left font-medium">Citation</th>
              <th className="px-3 py-2 text-left font-medium">Type</th>
            </tr>
          </thead>
          <tbody>
            {compliance.items.map((it, i) => (
              <tr
                key={it.id}
                className={
                  i % 2 === 0
                    ? "border-t border-neutral-100"
                    : "border-t border-neutral-100 bg-neutral-50/50"
                }
              >
                <td className="px-3 py-2 align-top">
                  <span className="font-mono text-xs text-neutral-700">
                    {it.item_id}
                  </span>
                </td>
                <td className="px-3 py-2 align-top text-neutral-800">
                  {it.statement}
                  {it.notes && (
                    <p className="mt-1 text-[11px] italic text-neutral-500">
                      {it.notes}
                    </p>
                  )}
                </td>
                <td className="px-3 py-2 align-top text-[11px] text-neutral-500">
                  {it.section_l_citation ?? (
                    <span className="text-neutral-400">—</span>
                  )}
                </td>
                <td className="px-3 py-2 align-top">
                  {it.pass_fail ? (
                    <Badge tone="red">Pass/fail</Badge>
                  ) : (
                    <Badge tone="neutral">Scored</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const CATEGORY_TONE: Record<RequirementCategory, "neutral" | "blue" | "amber" | "red" | "violet" | "green"> = {
  technical: "blue",
  operational: "neutral",
  security: "red",
  staffing: "violet",
  performance: "amber",
  reporting: "green",
  other: "neutral",
};

function RequirementsMatrixTable({
  requirements,
}: {
  requirements: RequirementsMatrixOut | null;
}) {
  if (!requirements || requirements.items.length === 0) {
    return null;
  }
  return (
    <section>
      <header className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-neutral-900">
          Requirements matrix · <Term kind="section" value="SOW">SOW</Term> /{" "}
          <Term kind="section" value="PWS">PWS</Term> obligations
        </h3>
        <span className="text-[11px] text-neutral-500">
          {requirements.items.length}{" "}
          {requirements.items.length === 1 ? "item" : "items"}
        </span>
      </header>
      <div className="overflow-hidden rounded-md border border-neutral-200">
        <table className="w-full table-fixed text-sm">
          <colgroup>
            <col className="w-16" />
            <col />
            <col className="w-44" />
            <col className="w-28" />
          </colgroup>
          <thead className="bg-neutral-50 text-[11px] uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-3 py-2 text-left font-medium">ID</th>
              <th className="px-3 py-2 text-left font-medium">Obligation</th>
              <th className="px-3 py-2 text-left font-medium">Citation</th>
              <th className="px-3 py-2 text-left font-medium">Category</th>
            </tr>
          </thead>
          <tbody>
            {requirements.items.map((it, i) => (
              <tr
                key={it.id}
                className={
                  i % 2 === 0
                    ? "border-t border-neutral-100"
                    : "border-t border-neutral-100 bg-neutral-50/50"
                }
              >
                <td className="px-3 py-2 align-top">
                  <span className="font-mono text-xs text-neutral-700">
                    {it.item_id}
                  </span>
                </td>
                <td className="px-3 py-2 align-top text-neutral-800">
                  {it.statement}
                </td>
                <td className="px-3 py-2 align-top text-[11px] text-neutral-500">
                  {it.source_citation ?? (
                    <span className="text-neutral-400">—</span>
                  )}
                </td>
                <td className="px-3 py-2 align-top">
                  <Badge tone={CATEGORY_TONE[it.category]}>{it.category}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EvaluationTables({ evaluation }: { evaluation: EvaluationOut | null }) {
  if (!evaluation) return null;
  const { pass_fail_items, scored_factors } = evaluation;
  if (pass_fail_items.length === 0 && scored_factors.length === 0) return null;

  return (
    <section>
      <header className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-neutral-900">
          Evaluation factors · <Term kind="section" value="M">Section M</Term>
        </h3>
        <span className="text-[11px] text-neutral-500">
          {pass_fail_items.length} pass/fail · {scored_factors.length} scored
        </span>
      </header>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {pass_fail_items.length > 0 && (
          <div className="overflow-hidden rounded-md border border-neutral-200">
            <header className="border-b border-neutral-100 bg-neutral-50 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-neutral-500">
              Pass / fail
            </header>
            <ul className="divide-y divide-neutral-100">
              {pass_fail_items.map((it) => (
                <li key={it.id} className="px-3 py-2 text-sm text-neutral-800">
                  <p>{it.statement}</p>
                  {it.source_citation && (
                    <p className="mt-1 text-[11px] text-neutral-500">
                      {it.source_citation}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {scored_factors.length > 0 && (
          <div className="overflow-hidden rounded-md border border-neutral-200">
            <header className="border-b border-neutral-100 bg-neutral-50 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-neutral-500">
              Scored factors
            </header>
            <ul className="divide-y divide-neutral-100">
              {scored_factors.map((it) => (
                <li key={it.id} className="px-3 py-2 text-sm text-neutral-800">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="font-semibold">{it.name}</p>
                    {it.weight != null && (
                      <Badge tone="violet">
                        <span className="tabular-nums">{it.weight}</span>
                        {it.weight <= 100 && it.weight > 0 ? "%" : ""}
                      </Badge>
                    )}
                  </div>
                  {it.description && (
                    <p className="mt-1 text-[11px] text-neutral-600">
                      {it.description}
                    </p>
                  )}
                  {it.source_citation && (
                    <p className="mt-1 text-[11px] text-neutral-500">
                      {it.source_citation}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
