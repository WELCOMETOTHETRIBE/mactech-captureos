import Link from "next/link";
import { notFound } from "next/navigation";

import { CapturePackageDownloadButton } from "@/components/capture-package-download";
import {
  Badge,
  Card,
  PageHeader,
  fmtDate,
  fmtMoney,
} from "@/components/ui";
import {
  apiFetch,
  type CapturePackageOut,
  type CPCaptureStrategySection,
  type CPComplianceMatrixSection,
  type CPCyberSection,
  type CPGovernanceReadinessSection,
  type CPKeyPersonnelSection,
  type CPOpportunitySection,
  type CPPackageCompleteness,
  type CPPastPerformanceSection,
  type CPQAHistorySection,
  type CPRequirementsMatrixSection,
  type CPTeamingPartnersSection,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function CapturePackagePage(props: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await props.params;

  let pkg: CapturePackageOut;
  try {
    pkg = await apiFetch<CapturePackageOut>(
      `/pursuits/${id}/capture-package`,
      { timeoutMs: 30_000 }
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  return (
    <div className="space-y-6">
      <Link
        href="/pipeline"
        className="text-xs text-neutral-500 hover:text-neutral-800"
      >
        ← Pipeline
      </Link>

      <PageHeader
        eyebrow="Capture Package"
        title={pkg.opportunity.title}
        subtitle={
          <span>
            {pkg.opportunity.agency ?? "Agency unknown"} ·{" "}
            <span className="font-mono text-xs">
              {pkg.opportunity.notice_id}
            </span>{" "}
            · schema v{pkg.schema_version}
          </span>
        }
        trailing={<CapturePackageDownloadButton pkg={pkg} />}
      />

      <CompletenessCard completeness={pkg.completeness} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <OpportunityCard section={pkg.opportunity} />
        <BidDecisionCard pkg={pkg} />
      </div>

      <CaptureStrategyCard section={pkg.capture_strategy} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CyberCard section={pkg.cyber} />
        <GovernanceReadinessCard section={pkg.governance_readiness} />
      </div>

      <ComplianceMatrixCard section={pkg.compliance_matrix} />
      <RequirementsMatrixCard section={pkg.requirements_matrix} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <PastPerformanceCard section={pkg.past_performance} />
        <KeyPersonnelCard section={pkg.key_personnel} />
        <TeamingPartnersCard section={pkg.teaming_partners} />
      </div>

      <QAHistoryCard section={pkg.qa_history} />

      <RawJsonCard pkg={pkg} />
    </div>
  );
}

/* ── Section cards ──────────────────────────────────────────────── */

function CompletenessCard({
  completeness,
}: {
  completeness: CPPackageCompleteness;
}) {
  const tone =
    completeness.overall_pct >= 80
      ? "green"
      : completeness.overall_pct >= 50
      ? "amber"
      : "red";
  return (
    <Card>
      <div className="flex flex-wrap items-start gap-6">
        <div className="flex flex-col items-center">
          <div
            className={`flex h-24 w-24 items-center justify-center rounded-full border-4 ${
              tone === "green"
                ? "border-emerald-500 text-emerald-700"
                : tone === "amber"
                ? "border-amber-500 text-amber-700"
                : "border-red-500 text-red-700"
            }`}
          >
            <span className="text-2xl font-semibold tabular-nums">
              {completeness.overall_pct.toFixed(0)}%
            </span>
          </div>
          <p className="mt-2 text-[11px] uppercase tracking-wider text-neutral-500">
            Completeness
          </p>
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {completeness.sections_complete.map((s) => (
              <Badge key={s} tone="green">
                ✓ {s}
              </Badge>
            ))}
            {completeness.sections_partial.map((s) => (
              <Badge key={s} tone="amber">
                {s}
              </Badge>
            ))}
            {completeness.sections_missing.map((s) => (
              <Badge key={s} tone="red">
                ✗ {s}
              </Badge>
            ))}
          </div>
          {completeness.gaps.length > 0 && (
            <div>
              <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
                Gaps
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-neutral-700">
                {completeness.gaps.map((g, i) => (
                  <li key={i}>{g}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function OpportunityCard({ section }: { section: CPOpportunitySection }) {
  return (
    <Card title="Opportunity">
      <dl className="grid grid-cols-1 gap-2 text-sm">
        <Row label="Title">{section.title}</Row>
        <Row label="Notice ID">
          <span className="font-mono text-xs">{section.notice_id}</span>
        </Row>
        {section.solicitation_number && (
          <Row label="Solicitation #">
            <span className="font-mono text-xs">
              {section.solicitation_number}
            </span>
          </Row>
        )}
        {section.agency && <Row label="Agency">{section.agency}</Row>}
        {section.naics_code && <Row label="NAICS">{section.naics_code}</Row>}
        {section.set_aside && <Row label="Set-aside">{section.set_aside}</Row>}
        {section.contract_type && (
          <Row label="Contract type">{section.contract_type}</Row>
        )}
        {section.notice_type && (
          <Row label="Notice type">{section.notice_type}</Row>
        )}
        {section.response_deadline && (
          <Row label="Deadline">{fmtDate(section.response_deadline)}</Row>
        )}
        {section.posted_at && (
          <Row label="Posted">{fmtDate(section.posted_at)}</Row>
        )}
        {(section.estimated_value_low || section.estimated_value_high) && (
          <Row label="Est. value">
            {section.estimated_value_low === section.estimated_value_high
              ? fmtMoney(section.estimated_value_low)
              : `${fmtMoney(section.estimated_value_low)} – ${fmtMoney(
                  section.estimated_value_high
                )}`}
          </Row>
        )}
        {section.submission_method && (
          <Row label="Submission">{section.submission_method}</Row>
        )}
      </dl>
    </Card>
  );
}

function BidDecisionCard({ pkg }: { pkg: CapturePackageOut }) {
  const d = pkg.bid_decision;
  const tone =
    d.decision === "bid"
      ? "green"
      : d.decision === "no_bid"
      ? "red"
      : "amber";
  return (
    <Card title="Bid decision">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Badge tone={tone}>{d.decision.toUpperCase()}</Badge>
          {d.pursuit_stage && (
            <span className="text-[11px] uppercase tracking-wider text-neutral-500">
              stage: {d.pursuit_stage}
            </span>
          )}
          {d.score != null && (
            <span className="text-xs text-neutral-600">
              score{" "}
              <span className="font-semibold tabular-nums">{d.score}</span> / 100
            </span>
          )}
        </div>
        {d.decider_founder_slug && (
          <p className="text-xs text-neutral-500">
            Owner: <span className="font-medium">{d.decider_founder_slug}</span>
          </p>
        )}
        {d.decided_at && (
          <p className="text-xs text-neutral-500">
            Last stage change: {fmtDate(d.decided_at)}
          </p>
        )}
        {d.rationale && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
              Rationale / notes
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-neutral-700">
              {d.rationale}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}

function CaptureStrategyCard({
  section,
}: {
  section: CPCaptureStrategySection;
}) {
  const empty =
    !section.scope_one_sentence &&
    !section.incumbent &&
    section.must_have_requirements.length === 0 &&
    section.nice_to_have.length === 0 &&
    section.red_flags_for_small_biz.length === 0 &&
    section.suggested_team_roles.length === 0;
  if (empty) {
    return (
      <Card title="Capture strategy">
        <p className="text-sm text-neutral-600">
          No brief or enrichment data yet. Generate the brief on the
          opportunity detail page.
        </p>
      </Card>
    );
  }
  return (
    <Card title="Capture strategy">
      <div className="space-y-4">
        {section.scope_one_sentence && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-brand-700">
              Scope
            </p>
            <p className="mt-1 text-base font-semibold text-neutral-900">
              {section.scope_one_sentence}
            </p>
          </div>
        )}
        {section.incumbent && section.incumbent.name && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
              Incumbent
            </p>
            <div className="mt-1 flex flex-wrap items-baseline gap-3 text-sm">
              <span className="font-semibold text-neutral-900">
                {section.incumbent.name}
              </span>
              {section.incumbent.uei && (
                <span className="font-mono text-xs text-neutral-500">
                  {section.incumbent.uei}
                </span>
              )}
              {section.incumbent.award_amount != null && (
                <span className="tabular-nums text-neutral-600">
                  {fmtMoney(section.incumbent.award_amount)}
                </span>
              )}
              {section.incumbent.end_date && (
                <span className="text-xs text-neutral-500">
                  ends {fmtDate(section.incumbent.end_date)}
                </span>
              )}
            </div>
          </div>
        )}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {section.must_have_requirements.length > 0 && (
            <BulletList
              label="Must-have requirements"
              items={section.must_have_requirements}
              tone="brand"
            />
          )}
          {section.nice_to_have.length > 0 && (
            <BulletList
              label="Nice-to-haves"
              items={section.nice_to_have}
              tone="neutral"
            />
          )}
          {section.red_flags_for_small_biz.length > 0 && (
            <BulletList
              label="Red flags for small biz"
              items={section.red_flags_for_small_biz}
              tone="amber"
            />
          )}
          {section.suggested_team_roles.length > 0 && (
            <BulletList
              label="Suggested teaming"
              items={section.suggested_team_roles}
              tone="violet"
            />
          )}
        </div>
      </div>
    </Card>
  );
}

function CyberCard({ section }: { section: CPCyberSection }) {
  const tone =
    section.sufficiency === "sufficient"
      ? "green"
      : section.sufficiency === "gap"
      ? "red"
      : "amber";
  return (
    <Card title="Cyber clauses + posture">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Badge tone={tone}>{section.sufficiency}</Badge>
          {section.cmmc_level_required && (
            <Badge tone="blue">requires {section.cmmc_level_required}</Badge>
          )}
        </div>
        {section.sufficiency_notes && (
          <p className="text-sm text-neutral-700">{section.sufficiency_notes}</p>
        )}
        {section.clauses_identified.length > 0 && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
              Clauses cited
            </p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {section.clauses_identified.map((c) => (
                <Badge key={c} tone="neutral">
                  {c}
                </Badge>
              ))}
            </div>
          </div>
        )}
        {section.posture_snapshot && (
          <p className="text-[11px] text-neutral-500">
            Codex SPRS{" "}
            <span className="font-semibold tabular-nums">
              {section.posture_snapshot.sprs_score ?? "—"}
            </span>
            {section.posture_snapshot.sprs_max != null && (
              <span> / {section.posture_snapshot.sprs_max}</span>
            )}{" "}
            · snapshot {fmtDate(section.posture_snapshot.snapshot_at)}
          </p>
        )}
      </div>
    </Card>
  );
}

function GovernanceReadinessCard({
  section,
}: {
  section: CPGovernanceReadinessSection;
}) {
  return (
    <Card title="Governance readiness">
      {section.source === "stub" ? (
        <p className="text-sm text-neutral-600">
          GovernanceOS isn&rsquo;t wired up yet (Integration Contract #2).
          Until then, readiness facts (DCAA accounting, FCL, set-aside
          eligibility, E-Verify, reps & certs) live outside this package.
        </p>
      ) : (
        <dl className="grid grid-cols-1 gap-2 text-sm">
          {section.accounting_system_dcaa_ready != null && (
            <Row label="DCAA accounting">
              {section.accounting_system_dcaa_ready ? (
                <Badge tone="green">ready</Badge>
              ) : (
                <Badge tone="red">not ready</Badge>
              )}
            </Row>
          )}
          {section.fcl_status && (
            <Row label="FCL">{section.fcl_status}</Row>
          )}
          {section.set_asides_held.length > 0 && (
            <Row label="Set-asides held">
              <div className="flex flex-wrap justify-end gap-1.5">
                {section.set_asides_held.map((s) => (
                  <Badge key={s} tone="neutral">
                    {s}
                  </Badge>
                ))}
              </div>
            </Row>
          )}
          {section.e_verify_enrolled != null && (
            <Row label="E-Verify">
              {section.e_verify_enrolled ? "enrolled" : "not enrolled"}
            </Row>
          )}
          {section.reps_certs_current != null && (
            <Row label="Reps & certs">
              {section.reps_certs_current ? "current" : "stale"}
            </Row>
          )}
        </dl>
      )}
    </Card>
  );
}

function ComplianceMatrixCard({
  section,
}: {
  section: CPComplianceMatrixSection;
}) {
  if (section.items.length === 0) {
    return (
      <Card title="Compliance matrix · Section L">
        <p className="text-sm text-neutral-600">
          Status: <Badge tone="neutral">{section.status}</Badge>. Generate the
          matrix on the opportunity detail page.
        </p>
      </Card>
    );
  }
  return (
    <Card
      title={`Compliance matrix · Section L (${section.items.length})`}
      trailing={
        <span className="text-[11px] text-neutral-500">
          extracted {fmtDate(section.last_generated_at)}
        </span>
      }
    >
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
            {section.items.map((it, i) => (
              <tr
                key={it.id}
                className={
                  i % 2 === 0
                    ? "border-t border-neutral-100"
                    : "border-t border-neutral-100 bg-neutral-50/50"
                }
              >
                <td className="px-3 py-2 align-top font-mono text-xs">
                  {it.id}
                </td>
                <td className="px-3 py-2 align-top">{it.statement}</td>
                <td className="px-3 py-2 align-top text-[11px] text-neutral-500">
                  {it.section_l_citation ?? "—"}
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
    </Card>
  );
}

function RequirementsMatrixCard({
  section,
}: {
  section: CPRequirementsMatrixSection;
}) {
  if (section.items.length === 0) {
    return (
      <Card title="Requirements matrix · SOW / PWS">
        <p className="text-sm text-neutral-600">
          Status: <Badge tone="neutral">{section.status}</Badge>. Generate the
          matrix on the opportunity detail page.
        </p>
      </Card>
    );
  }
  return (
    <Card
      title={`Requirements matrix · SOW / PWS (${section.items.length})`}
      trailing={
        <span className="text-[11px] text-neutral-500">
          extracted {fmtDate(section.last_generated_at)}
        </span>
      }
    >
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
            {section.items.map((it, i) => (
              <tr
                key={it.id}
                className={
                  i % 2 === 0
                    ? "border-t border-neutral-100"
                    : "border-t border-neutral-100 bg-neutral-50/50"
                }
              >
                <td className="px-3 py-2 align-top font-mono text-xs">
                  {it.id}
                </td>
                <td className="px-3 py-2 align-top">{it.statement}</td>
                <td className="px-3 py-2 align-top text-[11px] text-neutral-500">
                  {it.source_citation ?? "—"}
                </td>
                <td className="px-3 py-2 align-top">
                  <Badge tone="neutral">{it.category}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function PastPerformanceCard({
  section,
}: {
  section: CPPastPerformanceSection;
}) {
  return (
    <Card title="Past performance">
      <p className="text-sm text-neutral-600">
        <span className="font-semibold text-neutral-900">
          {section.selected.length}
        </span>{" "}
        selected · {section.library_size} in library
      </p>
      {section.selected.length === 0 && section.library_size > 0 && (
        <p className="mt-2 text-[11px] text-neutral-500">
          Per-pursuit selection isn&rsquo;t built yet. ProposalOS will pick
          from the library at proposal kickoff.
        </p>
      )}
      {section.selected.length === 0 && section.library_size === 0 && (
        <p className="mt-2 text-[11px] text-neutral-500">
          Library is empty. Add past performance records under{" "}
          <Link
            href="/library"
            className="text-brand-700 hover:underline"
          >
            Library
          </Link>
          .
        </p>
      )}
      {section.selected.map((p) => (
        <div key={p.id} className="mt-3 border-t border-neutral-100 pt-2">
          <p className="text-sm font-semibold">{p.title}</p>
          <p className="text-[11px] text-neutral-500">
            {p.customer_agency ?? "—"} · {fmtMoney(p.contract_value)}
          </p>
        </div>
      ))}
    </Card>
  );
}

function KeyPersonnelCard({ section }: { section: CPKeyPersonnelSection }) {
  return (
    <Card title="Key personnel">
      <p className="text-sm text-neutral-600">
        <span className="font-semibold text-neutral-900">
          {section.selected.length}
        </span>{" "}
        selected · {section.library_size} in library
      </p>
      {section.selected.length === 0 && (
        <p className="mt-2 text-[11px] text-neutral-500">
          Per-pursuit selection isn&rsquo;t built yet. {section.library_size}{" "}
          founders/people available in the library.
        </p>
      )}
      {section.selected.map((p) => (
        <div key={p.id} className="mt-3 border-t border-neutral-100 pt-2">
          <p className="text-sm font-semibold">{p.full_name}</p>
          <p className="text-[11px] text-neutral-500">
            {p.title ?? "—"}
            {p.pillar && ` · ${p.pillar}`}
          </p>
        </div>
      ))}
    </Card>
  );
}

function TeamingPartnersCard({
  section,
}: {
  section: CPTeamingPartnersSection;
}) {
  return (
    <Card title="Teaming partners">
      <p className="text-sm text-neutral-600">
        <span className="font-semibold text-neutral-900">
          {section.selected.length}
        </span>{" "}
        selected · {section.library_size} in library
      </p>
      {section.selected.length === 0 && (
        <p className="mt-2 text-[11px] text-neutral-500">
          Per-pursuit selection isn&rsquo;t built yet. Legal-doc state will
          arrive when GovernanceOS lands (Contract #2).
        </p>
      )}
      {section.selected.map((p) => (
        <div key={p.id} className="mt-3 border-t border-neutral-100 pt-2">
          <p className="text-sm font-semibold">{p.name}</p>
          {p.uei && (
            <p className="text-[11px] font-mono text-neutral-500">{p.uei}</p>
          )}
        </div>
      ))}
    </Card>
  );
}

function QAHistoryCard({ section }: { section: CPQAHistorySection }) {
  if (section.entries.length === 0) {
    return (
      <Card title="Q&A history">
        <p className="text-sm text-neutral-600">
          No Q&amp;A captured yet. Use the Ask-Claude panel on the opportunity
          detail page to ask and answer questions.
        </p>
      </Card>
    );
  }
  return (
    <Card title={`Q&A history (${section.entries.length})`}>
      <div className="space-y-4">
        {section.entries.map((q) => (
          <div key={q.id} className="border-l-2 border-neutral-200 pl-3">
            <p className="text-sm font-medium text-neutral-900">{q.question}</p>
            {q.answer && (
              <p className="mt-1 whitespace-pre-wrap text-sm text-neutral-700">
                {q.answer}
              </p>
            )}
            {q.submitted_at && (
              <p className="mt-1 text-[11px] text-neutral-500">
                {fmtDate(q.submitted_at)}
                {q.asked_by_founder_slug && ` · @${q.asked_by_founder_slug}`}
              </p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function RawJsonCard({ pkg }: { pkg: CapturePackageOut }) {
  return (
    <Card>
      <details>
        <summary className="cursor-pointer text-sm font-medium text-neutral-700">
          View raw package JSON
        </summary>
        <pre className="mt-3 max-h-96 overflow-auto rounded-md border border-neutral-200 bg-neutral-50 p-3 font-mono text-[11px] leading-relaxed text-neutral-700">
          {JSON.stringify(pkg, null, 2)}
        </pre>
      </details>
    </Card>
  );
}

/* ── shared row + bullet primitives ──────────────────────────────── */

function Row({
  label,
  children,
}: {
  label: string;
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

function BulletList({
  label,
  items,
  tone,
}: {
  label: string;
  items: string[];
  tone: "brand" | "neutral" | "amber" | "violet";
}) {
  const dotClass: Record<typeof tone, string> = {
    brand: "bg-brand-500",
    neutral: "bg-neutral-400",
    amber: "bg-amber-500",
    violet: "bg-violet-500",
  };
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
        {label}
      </p>
      <ul className="mt-1 space-y-1.5 text-sm text-neutral-800">
        {items.map((it, i) => (
          <li key={i} className="flex gap-2">
            <span
              className={`mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full ${dotClass[tone]}`}
            />
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
