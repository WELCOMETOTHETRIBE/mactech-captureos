import Link from "next/link";
import { apiFetch, type ForecastsResponse } from "@/lib/api";
import { Card, NaicsBadge, PageHeader, fmtDate, fmtMoney } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function ForecastsPage({
  searchParams
}: {
  searchParams?: Promise<{ all?: string }>;
}) {
  const sp = (await searchParams) ?? {};
  const showAll = sp.all === "1";
  const data = await apiFetch<ForecastsResponse>(
    `/forecasts?upcoming_only=true&naics_filter=${showAll ? "false" : "true"}&limit=120`
  ).catch(
    () => ({ total: 0, items: [], target_naics_filter: false, target_naics: [] }) as ForecastsResponse
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Pre-SAM intent"
        title="Agency forecasts"
        subtitle={
          <span>
            Procurement forecasts published by DHS APFS, VA FCO, USACE,
            AFBES, GSA, HHS — typically 30 to 180 days before the
            matching SAM solicitation. Captured daily via Apify.
          </span>
        }
      />

      {data.target_naics_filter ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
          <span>
            Filtered to your {data.target_naics.length} target NAICS:{" "}
            <span className="text-neutral-700">{data.target_naics.join(", ")}</span>
          </span>
          <Link href="/forecasts?all=1" className="text-brand-700 hover:underline">
            Show all forecasts
          </Link>
        </div>
      ) : data.target_naics.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
          <span>Showing all forecasts.</span>
          <Link href="/forecasts" className="text-brand-700 hover:underline">
            Filter to your NAICS
          </Link>
        </div>
      ) : null}

      {data.items.length === 0 ? (
        <Card>
          <p className="text-sm text-neutral-500">
            No forecasts captured yet. The Apify daily beat (0530 ET)
            populates this on completion. Check back tomorrow, or
            verify <code>APIFY_API_TOKEN</code> is set on the workers
            service.
          </p>
        </Card>
      ) : (
        <ul className="space-y-3">
          {data.items.map((fc) => (
            <li key={fc.id}>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                      {fc.agency ?? "Unknown agency"}
                      {fc.contracting_office ? ` · ${fc.contracting_office}` : ""}
                      {fc.matches_target_naics ? (
                        <span className="ml-2 rounded-sm bg-brand-50 px-1.5 py-0.5 font-semibold text-brand-800">
                          target NAICS
                        </span>
                      ) : null}
                    </p>
                    <h3 className="mt-1 text-sm font-semibold text-neutral-900">
                      {fc.title}
                    </h3>
                    {fc.description ? (
                      <p className="mt-2 text-sm leading-snug text-neutral-700">
                        {fc.description}
                      </p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500">
                      {fc.naics_code ? (
                        <span>
                          <NaicsBadge code={fc.naics_code} />
                        </span>
                      ) : null}
                      {fc.set_aside ? <span>Set-aside: {fc.set_aside}</span> : null}
                      {fc.contract_type ? <span>Type: {fc.contract_type}</span> : null}
                      {fc.estimated_value_text ? (
                        <span>Value: {fc.estimated_value_text}</span>
                      ) : fc.estimated_value_high !== null ? (
                        <span>
                          Value: {fmtMoney(fc.estimated_value_low ?? null)} –{" "}
                          {fmtMoney(fc.estimated_value_high)}
                        </span>
                      ) : null}
                      {fc.expected_solicitation_date ? (
                        <span className="text-amber-700">
                          RFP expected: {fmtDate(fc.expected_solicitation_date)}
                        </span>
                      ) : null}
                      {fc.incumbent_name ? (
                        <span>Incumbent: {fc.incumbent_name}</span>
                      ) : null}
                    </div>
                    {fc.poc_email || fc.poc_name ? (
                      <p className="mt-2 text-xs text-neutral-500">
                        POC: {fc.poc_name ?? ""}
                        {fc.poc_name && fc.poc_email ? " · " : ""}
                        {fc.poc_email ? (
                          <a
                            href={`mailto:${fc.poc_email}`}
                            className="text-brand-700 hover:underline"
                          >
                            {fc.poc_email}
                          </a>
                        ) : null}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-col items-end gap-1 text-xs">
                    <a
                      href={fc.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-neutral-500 hover:text-neutral-800"
                    >
                      Source ({fc.source_host ?? "link"})
                    </a>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
