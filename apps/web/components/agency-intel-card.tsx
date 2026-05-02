import type { AgencyIntelOut } from "@/lib/api";
import { pullAgencyIntel } from "@/lib/agency-intel";
import { fmtDate, fmtMoney } from "@/components/ui";

/**
 * Agency intel card — extracted from the opportunity detail page in
 * Sprint B so it can also live on the pursuit detail page (its more
 * natural home, since you only need this signal once you're committed).
 *
 * Reads the cached USASpending lookup for the agency + NAICS pair and
 * renders top recipients + spending stats. Cache TTL is 7d server-side;
 * the Refresh button forces a re-pull.
 */
export function AgencyIntelCard({
  opportunityId,
  agency,
  naics,
  intel,
}: {
  opportunityId: string;
  agency: string | null;
  naics: string | null;
  intel: AgencyIntelOut | null;
}) {
  if (!agency || !naics) return null;
  const action = pullAgencyIntel.bind(null, opportunityId);
  return (
    <section className="rounded-md border border-paper-200 bg-white p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-brand-700">
            Agency intel
          </p>
          <p className="mt-1 text-sm text-neutral-600">
            How {agency.split(".")[0]} has spent under NAICS {naics} in the
            last 12 months. Pulled from USASpending; cached 7 days.
          </p>
        </div>
        {intel && (
          <form action={action}>
            <button
              type="submit"
              className="rounded-md px-2 py-1 text-[11px] text-neutral-500 hover:bg-paper-100 hover:text-neutral-800"
              title="Re-fetch from USASpending. Takes 5–10 seconds."
            >
              ↻ Refresh
            </button>
          </form>
        )}
      </div>

      {!intel ? (
        <Empty action={action} />
      ) : intel.lookup_failed ? (
        <Failure intel={intel} action={action} />
      ) : intel.award_count === 0 ? (
        <NoMatches intel={intel} />
      ) : (
        <Body intel={intel} />
      )}
    </section>
  );
}

function Empty({ action }: { action: () => Promise<void> }) {
  return (
    <div className="mt-4 rounded-md border border-dashed border-paper-300 bg-paper-50 p-5 text-center">
      <p className="text-sm font-medium text-neutral-800">
        Agency intel not loaded yet
      </p>
      <p className="mt-2 text-sm text-neutral-600">
        Click below to pull spending history from USASpending.gov for this
        agency + NAICS combination. Takes 5–10 seconds the first time;
        subsequent loads are instant for 7 days.
      </p>
      <form action={action} className="mt-4">
        <button
          type="submit"
          className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
        >
          Pull agency intel →
        </button>
      </form>
    </div>
  );
}

function Failure({
  intel,
  action,
}: {
  intel: AgencyIntelOut;
  action: () => Promise<void>;
}) {
  return (
    <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
      <p className="font-medium">USASpending lookup didn&rsquo;t resolve.</p>
      <p className="mt-1 text-xs">
        {intel.failure_note ??
          "The agency name may not match a USASpending toptier exactly."}
      </p>
      <form action={action} className="mt-3">
        <button
          type="submit"
          className="rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-900 hover:border-amber-500"
        >
          Retry
        </button>
      </form>
    </div>
  );
}

function NoMatches({ intel }: { intel: AgencyIntelOut }) {
  return (
    <p className="mt-4 text-sm text-neutral-600">
      USASpending returned <strong className="text-neutral-900">0 awards</strong>{" "}
      for {intel.agency_name} under NAICS {intel.naics_code} in the last{" "}
      {intel.lookback_days} days. Either this agency hasn&rsquo;t bought
      under this NAICS recently, or the agency name doesn&rsquo;t match a
      USASpending toptier exactly.
    </p>
  );
}

function Body({ intel }: { intel: AgencyIntelOut }) {
  return (
    <div className="mt-5 space-y-5">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat
          label="Awards (12mo)"
          value={intel.award_count.toLocaleString()}
          hint={
            intel.sample_size && intel.sample_size < intel.award_count
              ? `top ${intel.sample_size} sampled`
              : undefined
          }
        />
        <Stat
          label="Total obligated"
          value={
            intel.total_obligated != null
              ? fmtMoney(intel.total_obligated)
              : "—"
          }
          hint="across the sample"
        />
        <Stat
          label="Average award"
          value={
            intel.avg_award_value != null ? fmtMoney(intel.avg_award_value) : "—"
          }
        />
        <Stat
          label="Median award"
          value={
            intel.median_award_value != null
              ? fmtMoney(intel.median_award_value)
              : "—"
          }
          hint="less skewed by outliers"
        />
      </div>

      {intel.top_recipients.length > 0 && (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
            Top recipients
          </p>
          <ol className="mt-2 space-y-1.5">
            {intel.top_recipients.map((r, i) => (
              <li
                key={`${r.name}-${i}`}
                className="flex items-baseline justify-between gap-3 text-sm"
              >
                <span className="flex min-w-0 items-baseline gap-2">
                  <span className="text-neutral-400 tabular-nums">
                    {i + 1}.
                  </span>
                  <span className="truncate font-medium text-neutral-900">
                    {r.name}
                  </span>
                  <span className="shrink-0 text-[11px] text-neutral-500 tabular-nums">
                    {r.award_count} {r.award_count === 1 ? "award" : "awards"}
                  </span>
                </span>
                <span className="shrink-0 tabular-nums font-semibold text-neutral-800">
                  {fmtMoney(r.total)}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <p className="border-t border-paper-200 pt-3 text-[11px] text-neutral-400">
        Refreshed {fmtDate(intel.refreshed_at)} ·{" "}
        {intel.is_fresh
          ? `cache hit (${Math.round(intel.cache_age_hours)}h old)`
          : "stale, refresh on next view"}{" "}
        · Source: USASpending.gov
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-paper-200 bg-paper-50 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-neutral-500">
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-neutral-900">
        {value}
      </p>
      {hint && <p className="text-[10px] text-neutral-500">{hint}</p>}
    </div>
  );
}
