import Link from "next/link";
import { notFound } from "next/navigation";

import {
  apiFetch,
  type AgencyIntelOut,
  type AmendmentListOut,
  type AuditTrailOut,
  type BidDecision,
  type ComplianceMatrixOut,
  type EvaluationOut,
  type FoundersListResponse,
  type PastPerformanceList,
  type PursuitDetailOut,
  type PursuitStage,
  type RequirementsMatrixOut,
  type SolicitationExtractionOut,
  type TeamingPartnerList,
  type WebMentionsResponse,
} from "@/lib/api";
import {
  deletePursuit,
  replacePursuitKeyPersonnel,
  replacePursuitPastPerformance,
  replacePursuitTeamingPartners,
  updatePursuit,
  updatePursuitBidDecision,
  updatePursuitWinStrategy,
} from "@/lib/pursuits";
import { AgencyIntelCard } from "@/components/agency-intel-card";
import { AmendmentsPanel } from "@/components/amendments-panel";
import { AuditTrailCard } from "@/components/audit-trail-card";
import { BidDecisionForm } from "@/components/bid-decision-form";
import { SolicitationPanel } from "@/components/solicitation-panel";
import { WebMentionsCard } from "@/components/web-mentions-card";
import {
  Badge,
  Card,
  PageHeader,
  Pillar,
  fmtDate,
  fmtMoney,
} from "@/components/ui";

export const dynamic = "force-dynamic";

const STAGE_TONE: Record<PursuitStage, "neutral" | "blue" | "amber" | "violet" | "brand" | "green" | "red"> = {
  lead: "neutral",
  qualify: "blue",
  pursue: "amber",
  propose: "violet",
  submit: "brand",
  won: "green",
  lost: "red",
};

const STAGE_LABEL: Record<PursuitStage, string> = {
  lead: "Lead",
  qualify: "Qualify",
  pursue: "Pursue",
  propose: "Propose",
  submit: "Submit",
  won: "Won",
  lost: "Lost",
};

export default async function PursuitDetailPage(props: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await props.params;

  let detail: PursuitDetailOut;
  try {
    detail = await apiFetch<PursuitDetailOut>(`/pursuits/${id}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  const opportunityId = detail.opportunity.id;
  const [
    pastPerformanceLib,
    foundersLib,
    teamingLib,
    auditTrail,
    extraction,
    compliance,
    requirements,
    evaluation,
    amendmentsList,
    agencyIntel,
    webMentions,
  ] = await Promise.all([
    apiFetch<PastPerformanceList>("/past-performance").catch(
      () => ({ total: 0, items: [] }) as PastPerformanceList
    ),
    apiFetch<FoundersListResponse>("/founders").catch(
      () => ({ total: 0, items: [] }) as FoundersListResponse
    ),
    apiFetch<TeamingPartnerList>("/teaming-partners").catch(
      () => ({ total: 0, active_count: 0, items: [] }) as TeamingPartnerList
    ),
    apiFetch<AuditTrailOut>(`/pursuits/${id}/audit`).catch(
      () => null as AuditTrailOut | null
    ),
    apiFetch<SolicitationExtractionOut>(
      `/opportunities/${opportunityId}/solicitation-extraction`
    ).catch(() => null as SolicitationExtractionOut | null),
    apiFetch<ComplianceMatrixOut>(
      `/opportunities/${opportunityId}/compliance-matrix`
    ).catch(() => null as ComplianceMatrixOut | null),
    apiFetch<RequirementsMatrixOut>(
      `/opportunities/${opportunityId}/requirements-matrix`
    ).catch(() => null as RequirementsMatrixOut | null),
    apiFetch<EvaluationOut>(`/opportunities/${opportunityId}/evaluation`).catch(
      () => null as EvaluationOut | null
    ),
    apiFetch<AmendmentListOut>(
      `/opportunities/${opportunityId}/amendments`
    ).catch(() => null as AmendmentListOut | null),
    apiFetch<AgencyIntelOut>(`/opportunities/${opportunityId}/agency-intel`, {
      timeoutMs: 4_000,
    }).catch(() => null as AgencyIntelOut | null),
    apiFetch<WebMentionsResponse>(
      `/opportunities/${opportunityId}/web-mentions`
    ).catch(() => null as WebMentionsResponse | null),
  ]);

  const winStrategyAction = async (formData: FormData) => {
    "use server";
    const themesText = String(formData.get("win_themes") ?? "");
    const discrimsText = String(formData.get("discriminators") ?? "");
    const winThemes = themesText
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    const discriminators = discrimsText
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    await updatePursuitWinStrategy(id, opportunityId, winThemes, discriminators);
  };

  const replacePastPerformanceAction = async (formData: FormData) => {
    "use server";
    const ids = formData.getAll("past_performance_id").map(String);
    await replacePursuitPastPerformance(id, ids);
  };

  const replaceKeyPersonnelAction = async (formData: FormData) => {
    "use server";
    const ids = formData.getAll("founder_id").map(String);
    await replacePursuitKeyPersonnel(id, ids);
  };

  const replaceTeamingPartnersAction = async (formData: FormData) => {
    "use server";
    const ids = formData.getAll("teaming_partner_id").map(String);
    await replacePursuitTeamingPartners(id, ids);
  };

  const notesAction = async (formData: FormData) => {
    "use server";
    const notes = String(formData.get("notes") ?? "");
    await updatePursuit({
      pursuitId: id,
      opportunityId,
      notes,
    });
  };

  const bidDecisionAction = async (formData: FormData) => {
    "use server";
    const raw = String(formData.get("bid_decision") ?? "pending");
    const decision: BidDecision =
      raw === "bid" || raw === "no_bid" || raw === "pending" ? raw : "pending";
    const rationale = String(formData.get("bid_rationale") ?? "").trim() || null;
    await updatePursuitBidDecision(id, opportunityId, decision, rationale);
  };

  const deleteAction = async () => {
    "use server";
    await deletePursuit({ pursuitId: id, opportunityId });
  };

  return (
    <div className="space-y-6">
      <Link
        href="/pipeline"
        className="text-xs text-neutral-500 hover:text-neutral-800"
      >
        ← Pipeline
      </Link>

      <PageHeader
        eyebrow="Pursuit"
        display
        title={detail.opportunity.title}
        subtitle={
          <span>
            {detail.opportunity.agency ?? "Agency unknown"} ·{" "}
            <span className="font-mono text-xs">
              {detail.opportunity.notice_id}
            </span>
          </span>
        }
        trailing={
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/pursuits/${detail.id}/capture-package`}
              className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
            >
              Capture Package →
            </Link>
            <Link
              href={`/opportunities/${detail.opportunity.id}`}
              className="rounded-md border border-neutral-300 px-3 py-2 text-sm text-neutral-700 hover:border-neutral-500"
            >
              Opportunity →
            </Link>
          </div>
        }
      />

      <PursuitMetaStrip detail={detail} />

      <BidDecisionForm detail={detail} action={bidDecisionAction} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <NotesEditor notes={detail.notes} action={notesAction} />
        <WinStrategyEditor
          winThemes={detail.win_themes}
          discriminators={detail.discriminators}
          action={winStrategyAction}
        />
      </div>

      <AmendmentsPanel amendments={amendmentsList} />

      <SolicitationPanel
        opportunityId={opportunityId}
        hasDescription
        extraction={extraction}
        compliance={compliance}
        requirements={requirements}
        evaluation={evaluation}
      />

      <PastPerformanceSelector
        selected={detail.selected_past_performance}
        library={pastPerformanceLib.items}
        action={replacePastPerformanceAction}
      />

      <KeyPersonnelSelector
        selected={detail.selected_key_personnel}
        library={foundersLib.items}
        action={replaceKeyPersonnelAction}
      />

      <TeamingPartnerSelector
        selected={detail.selected_teaming_partners}
        library={teamingLib.items}
        action={replaceTeamingPartnersAction}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AgencyIntelCard
          opportunityId={opportunityId}
          agency={detail.opportunity.agency}
          naics={detail.opportunity.naics_code}
          intel={agencyIntel}
        />
        <WebMentionsCard opportunityId={opportunityId} mentions={webMentions} />
      </div>

      <AuditTrailCard trail={auditTrail} />

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">
              Danger zone
            </p>
            <p className="mt-1 text-sm text-neutral-700">
              Remove this pursuit from the pipeline. The opportunity stays in
              the catalog; only the pursuit, win themes, and selections are
              dropped.
            </p>
          </div>
          <form action={deleteAction}>
            <button
              type="submit"
              className="rounded-md border border-red-300 px-3 py-2 text-xs font-medium text-red-700 hover:border-red-500 hover:bg-red-50"
            >
              Delete pursuit
            </button>
          </form>
        </div>
      </Card>
    </div>
  );
}

/* ── Sub-sections ───────────────────────────────────────────────── */

function PursuitMetaStrip({ detail }: { detail: PursuitDetailOut }) {
  return (
    <Card>
      <dl className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
        <Meta label="Stage">
          <Badge tone={STAGE_TONE[detail.stage]}>
            {STAGE_LABEL[detail.stage]}
          </Badge>
        </Meta>
        <Meta label="Owner">
          {detail.owner_founder_slug ? (
            <span className="font-medium">{detail.owner_founder_name}</span>
          ) : (
            <span className="italic text-neutral-500">unassigned</span>
          )}
        </Meta>
        <Meta label="NAICS">
          {detail.opportunity.naics_code ?? (
            <span className="text-neutral-400">—</span>
          )}
        </Meta>
        <Meta label="Deadline">
          {fmtDate(detail.opportunity.response_deadline)}
        </Meta>
      </dl>
    </Card>
  );
}

function Meta({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-neutral-500">
        {label}
      </dt>
      <dd className="mt-1">{children}</dd>
    </div>
  );
}

function NotesEditor({
  notes,
  action,
}: {
  notes: string | null;
  action: (formData: FormData) => Promise<void>;
}) {
  return (
    <Card title="Notes">
      <form action={action} className="space-y-3">
        <textarea
          name="notes"
          defaultValue={notes ?? ""}
          rows={6}
          placeholder="Bid rationale, customer notes, threat assessment, who said what at the industry day…"
          className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        <div className="flex justify-end">
          <button
            type="submit"
            className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
          >
            Save notes
          </button>
        </div>
      </form>
    </Card>
  );
}

function WinStrategyEditor({
  winThemes,
  discriminators,
  action,
}: {
  winThemes: string[];
  discriminators: string[];
  action: (formData: FormData) => Promise<void>;
}) {
  return (
    <Card title="Win strategy">
      <form action={action} className="space-y-4">
        <div>
          <label className="block">
            <span className="text-[11px] font-medium uppercase tracking-wide text-brand-700">
              Win themes
            </span>
            <p className="mt-0.5 text-[11px] text-neutral-500">
              One theme per line. ProposalOS uses these as the spine for
              per-volume ghost copy.
            </p>
            <textarea
              name="win_themes"
              defaultValue={winThemes.join("\n")}
              rows={5}
              placeholder={
                "Continuity-of-mission delivery from cleared veteran-led team\n" +
                "Demonstrated DFARS 7012 / NIST 800-171 compliance\n" +
                "Local on-site presence within 30 miles of customer site"
              }
              className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </label>
        </div>
        <div>
          <label className="block">
            <span className="text-[11px] font-medium uppercase tracking-wide text-violet-700">
              Discriminators
            </span>
            <p className="mt-0.5 text-[11px] text-neutral-500">
              One discriminator per line. What makes us better than likely
              competitors on this specific opportunity?
            </p>
            <textarea
              name="discriminators"
              defaultValue={discriminators.join("\n")}
              rows={5}
              placeholder={
                "SDVOSB-certified prime — set-aside eligible without teaming\n" +
                "GovCloud-resident infrastructure already accredited"
              }
              className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </label>
        </div>
        <div className="flex justify-end">
          <button
            type="submit"
            className="rounded-md border border-brand-700 bg-brand-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-800"
          >
            Save win strategy
          </button>
        </div>
      </form>
    </Card>
  );
}

function PastPerformanceSelector({
  selected,
  library,
  action,
}: {
  selected: PursuitDetailOut["selected_past_performance"];
  library: import("@/lib/api").PastPerformanceOut[];
  action: (formData: FormData) => Promise<void>;
}) {
  const selectedIds = new Set(selected.map((p) => p.id));
  return (
    <Card
      title={`Past performance (${selected.length} selected · ${library.length} in library)`}
    >
      {library.length === 0 ? (
        <p className="text-sm text-neutral-600">
          Library is empty.{" "}
          <Link
            href="/library/past-performance/new"
            className="text-brand-700 hover:underline"
          >
            Add a record →
          </Link>
        </p>
      ) : (
        <form action={action} className="space-y-3">
          <ul className="divide-y divide-neutral-100 rounded-md border border-neutral-200">
            {library.map((pp) => {
              const isSelected = selectedIds.has(pp.id);
              return (
                <li
                  key={pp.id}
                  className="flex items-start gap-3 px-3 py-2.5 hover:bg-neutral-50"
                >
                  <input
                    type="checkbox"
                    name="past_performance_id"
                    value={pp.id}
                    defaultChecked={isSelected}
                    className="mt-1 h-4 w-4 rounded border-neutral-300 text-brand-700 focus:ring-brand-500"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-neutral-900">
                      {pp.title}
                    </p>
                    <p className="text-[11px] text-neutral-500">
                      {pp.customer_agency ?? "—"}
                      {pp.contract_number && ` · #${pp.contract_number}`}
                      {pp.contract_value != null &&
                        ` · ${fmtMoney(pp.contract_value)}`}
                    </p>
                    {pp.summary && (
                      <p className="mt-1 line-clamp-2 text-xs text-neutral-600">
                        {pp.summary}
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="flex justify-end">
            <button
              type="submit"
              className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
            >
              Save selection
            </button>
          </div>
        </form>
      )}
    </Card>
  );
}

function KeyPersonnelSelector({
  selected,
  library,
  action,
}: {
  selected: PursuitDetailOut["selected_key_personnel"];
  library: import("@/lib/api").FounderRecord[];
  action: (formData: FormData) => Promise<void>;
}) {
  const selectedIds = new Set(selected.map((p) => p.id));
  return (
    <Card
      title={`Key personnel (${selected.length} selected · ${library.length} in library)`}
    >
      {library.length === 0 ? (
        <p className="text-sm text-neutral-600">No founders/people on file.</p>
      ) : (
        <form action={action} className="space-y-3">
          <ul className="divide-y divide-neutral-100 rounded-md border border-neutral-200">
            {library.map((f) => {
              const isSelected = selectedIds.has(f.id);
              return (
                <li
                  key={f.id}
                  className="flex items-start gap-3 px-3 py-2.5 hover:bg-neutral-50"
                >
                  <input
                    type="checkbox"
                    name="founder_id"
                    value={f.id}
                    defaultChecked={isSelected}
                    className="mt-1 h-4 w-4 rounded border-neutral-300 text-brand-700 focus:ring-brand-500"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-neutral-900">
                      {f.full_name}
                      <span className="ml-2 text-[11px] font-normal text-neutral-500">
                        @{f.slug}
                      </span>
                    </p>
                    <p className="mt-0.5 flex items-center gap-2 text-[11px] text-neutral-600">
                      <span>{f.title}</span>
                      <Pillar pillar={f.pillar} />
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="flex justify-end">
            <button
              type="submit"
              className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
            >
              Save selection
            </button>
          </div>
        </form>
      )}
    </Card>
  );
}

function TeamingPartnerSelector({
  selected,
  library,
  action,
}: {
  selected: PursuitDetailOut["selected_teaming_partners"];
  library: import("@/lib/api").TeamingPartnerOut[];
  action: (formData: FormData) => Promise<void>;
}) {
  const selectedIds = new Set(selected.map((p) => p.id));
  return (
    <Card
      title={`Teaming partners (${selected.length} selected · ${library.length} in library)`}
    >
      {library.length === 0 ? (
        <p className="text-sm text-neutral-600">
          No teaming partners on file.{" "}
          <Link
            href="/library/teaming-partners/new"
            className="text-brand-700 hover:underline"
          >
            Add one →
          </Link>
        </p>
      ) : (
        <form action={action} className="space-y-3">
          <ul className="divide-y divide-neutral-100 rounded-md border border-neutral-200">
            {library.map((p) => {
              const isSelected = selectedIds.has(p.id);
              return (
                <li
                  key={p.id}
                  className="flex items-start gap-3 px-3 py-2.5 hover:bg-neutral-50"
                >
                  <input
                    type="checkbox"
                    name="teaming_partner_id"
                    value={p.id}
                    defaultChecked={isSelected}
                    className="mt-1 h-4 w-4 rounded border-neutral-300 text-brand-700 focus:ring-brand-500"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-neutral-900">
                      {p.name}
                      {p.uei && (
                        <span className="ml-2 font-mono text-[11px] font-normal text-neutral-500">
                          {p.uei}
                        </span>
                      )}
                    </p>
                    {p.set_aside_certifications.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {p.set_aside_certifications.map((c) => (
                          <Badge key={c} tone="green">
                            {c}
                          </Badge>
                        ))}
                      </div>
                    )}
                    {p.capabilities.length > 0 && (
                      <p className="mt-1 line-clamp-2 text-xs text-neutral-600">
                        {p.capabilities.slice(0, 6).join(" · ")}
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="flex justify-end">
            <button
              type="submit"
              className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
            >
              Save selection
            </button>
          </div>
        </form>
      )}
    </Card>
  );
}
