import { Badge, Card, ExplainLink, Term, fmtDate } from "@/components/ui";
import type { SamRegistrationStatus, TenantEligibilityOut } from "@/lib/api";

const STATUS_TONE: Record<SamRegistrationStatus, "green" | "red" | "amber" | "neutral"> = {
  active: "green",
  expired: "red",
  invalid: "red",
  unverified: "amber",
};

const STATUS_LABEL: Record<SamRegistrationStatus, string> = {
  active: "Active",
  expired: "Expired",
  invalid: "Invalid / not found",
  unverified: "Unverified",
};

export function TenantEligibilityCard({
  eligibility,
}: {
  eligibility: TenantEligibilityOut;
}) {
  return (
    <Card
      title="Bid eligibility"
      trailing={
        eligibility.has_hard_blocker ? (
          <Badge tone="red">Hard blocker</Badge>
        ) : eligibility.blockers.length ? (
          <Badge tone="amber">{eligibility.blockers.length} warning(s)</Badge>
        ) : (
          <Badge tone="green">All clear</Badge>
        )
      }
    >
      <BlockerBanner eligibility={eligibility} />

      <div className="mt-4 grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
        <SamRegistrationRow eligibility={eligibility} />
        <ExclusionsRow eligibility={eligibility} />
        <SetAsideRow eligibility={eligibility} />
        <CyberRow eligibility={eligibility} />
      </div>

      {eligibility.blockers.length > 0 && (
        <div className="mt-4 border-t border-neutral-100 pt-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
            Action items
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-neutral-700">
            {eligibility.blockers.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>
      )}

      {eligibility.governance.source === "stub" && (
        <p className="mt-4 text-[11px] text-neutral-500">
          Governance readiness (FCL, accounting system, E-Verify) requires
          GovernanceOS — coming in a future sprint.
        </p>
      )}
    </Card>
  );
}

function BlockerBanner({
  eligibility,
}: {
  eligibility: TenantEligibilityOut;
}) {
  if (eligibility.has_hard_blocker) {
    return (
      <div className="rounded-md border border-red-300 bg-red-50 p-3">
        <p className="flex items-center gap-2 text-sm font-medium text-red-900">
          <span aria-hidden>!</span> Bidding is blocked until at least one item
          below is resolved.
        </p>
      </div>
    );
  }
  if (eligibility.blockers.length > 0) {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 p-3">
        <p className="flex items-center gap-2 text-sm font-medium text-amber-900">
          <span aria-hidden>!</span> {eligibility.blockers.length} warning
          {eligibility.blockers.length === 1 ? "" : "s"} — review before bidding.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3">
      <p className="flex items-center gap-2 text-sm font-medium text-emerald-900">
        <span aria-hidden>✓</span> All eligibility checks pass.
      </p>
    </div>
  );
}

function SamRegistrationRow({
  eligibility,
}: {
  eligibility: TenantEligibilityOut;
}) {
  const reg = eligibility.sam_registration;
  return (
    <Row label="SAM.gov registration">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={STATUS_TONE[reg.status]}>
          {STATUS_LABEL[reg.status]}
        </Badge>
        {reg.expires_at && reg.status === "active" && (
          <span className="text-[11px] text-neutral-500">
            expires {fmtDate(reg.expires_at)}
            {reg.days_until_expiration != null && (
              <>
                {" "}
                ({reg.days_until_expiration}d)
              </>
            )}
          </span>
        )}
      </div>
      <p className="mt-1 text-[10px] text-neutral-400">
        {reg.last_checked_at
          ? `last checked ${fmtDate(reg.last_checked_at)}`
          : "not yet verified"}
      </p>
    </Row>
  );
}

function ExclusionsRow({
  eligibility,
}: {
  eligibility: TenantEligibilityOut;
}) {
  const ex = eligibility.exclusions;
  return (
    <Row label="Federal exclusions">
      {ex.is_excluded ? (
        <Badge tone="red">DEBARRED ({ex.record_count} record(s))</Badge>
      ) : (
        <Badge tone="green">Clear</Badge>
      )}
      <p className="mt-1 text-[10px] text-neutral-400">
        {ex.last_checked_at
          ? `last checked ${fmtDate(ex.last_checked_at)}`
          : "not yet verified"}
      </p>
    </Row>
  );
}

function SetAsideRow({
  eligibility,
}: {
  eligibility: TenantEligibilityOut;
}) {
  return (
    <Row label="Set-asides held">
      {eligibility.set_aside_certifications.length === 0 ? (
        <span className="text-neutral-500">None on file</span>
      ) : (
        <div className="flex flex-wrap gap-1">
          {eligibility.set_aside_certifications.map((s) => (
            <ExplainLink key={s} slug={`set_aside_cert:${s}`}>
              <Badge tone="green">{s}</Badge>
            </ExplainLink>
          ))}
        </div>
      )}
    </Row>
  );
}

function CyberRow({
  eligibility,
}: {
  eligibility: TenantEligibilityOut;
}) {
  const c = eligibility.cyber;
  if (c.sprs_score == null) {
    return (
      <Row label={<Term kind="sprs" value="SPRS">SPRS score</Term>}>
        <span className="text-neutral-500">Not on file</span>
      </Row>
    );
  }
  const tone = c.sprs_score >= 80 ? "green" : c.sprs_score >= 0 ? "amber" : "red";
  return (
    <Row label={<Term kind="sprs" value="SPRS">SPRS score</Term>}>
      <Badge tone={tone}>
        <span className="tabular-nums font-semibold">{c.sprs_score}</span>
        <span className="ml-1 text-[10px] opacity-70">/ {c.sprs_max}</span>
      </Badge>
      {c.sprs_assessment_date && (
        <p className="mt-1 text-[10px] text-neutral-400">
          assessed {fmtDate(c.sprs_assessment_date)}
        </p>
      )}
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
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-neutral-500">
        {label}
      </dt>
      <dd className="mt-1">{children}</dd>
    </div>
  );
}
