import Link from "next/link";
import {
  apiFetch,
  type ForecastsResponse,
  type IntegrationsResponse,
} from "@/lib/api";
import {
  Card,
  EmptyState,
  LinkButton,
  NaicsBadge,
  PageHeader,
  ScoreBadge,
  fmtDate,
  fmtMoney
} from "@/components/ui";
import { TermPopover } from "@/components/term-popover";
import { IntegrationDiagnostic } from "@/components/integration-diagnostic";
import { triggerForecastsRun } from "@/lib/integrations";

export const dynamic = "force-dynamic";

export default async function ForecastsPage({
  searchParams
}: {
  searchParams?: Promise<{ all?: string }>;
}) {
  const sp = (await searchParams) ?? {};
  const showAll = sp.all === "1";

  type IntegrationsResult =
    | { ok: true; data: IntegrationsResponse }
    | { ok: false; error: string };

  const [data, integrationsResult] = await Promise.all([
    apiFetch<ForecastsResponse>(
      `/forecasts?upcoming_only=true&naics_filter=${showAll ? "false" : "true"}&limit=120`
    ).catch(
      () =>
        ({
          total: 0,
          items: [],
          target_naics_filter: false,
          target_naics: []
        }) as ForecastsResponse
    ),
    apiFetch<IntegrationsResponse>("/me/integrations")
      .then((d) => ({ ok: true, data: d }) as IntegrationsResult)
      .catch(
        (err) =>
          ({
            ok: false,
            error: err instanceof Error ? err.message : String(err)
          }) as IntegrationsResult
      )
  ]);

  const integrationsError = integrationsResult.ok ? null : integrationsResult.error;
  const forecastsStatus = integrationsResult.ok
    ? integrationsResult.data.integrations.find(
        (i) => i.capability === "forecasts"
      ) ?? null
    : null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Pre-SAM intent"
        title="Agency forecasts"
        subtitle={
          <span>
            Procurement forecasts published by DHS APFS, VA FCO, USACE,
            AFBES, GSA, HHS — typically 30 to 180 days before the matching
            SAM solicitation. Use them to position before the{" "}
            <TermPopover kind="clause" value="RFP">RFP</TermPopover> drops.
          </span>
        }
      />

      {data.target_naics_filter ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>
            Filtered to your {data.target_naics.length} target{" "}
            <TermPopover kind="naics" value="overview">NAICS</TermPopover>:{" "}
            <span className="text-foreground">{data.target_naics.join(", ")}</span>
          </span>
          <Link href="/forecasts?all=1" className="text-primary hover:underline">
            Show all forecasts
          </Link>
        </div>
      ) : data.target_naics.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Showing all forecasts.</span>
          <Link href="/forecasts" className="text-primary hover:underline">
            Filter to your{" "}
            <TermPopover kind="naics" value="overview">NAICS</TermPopover>
          </Link>
        </div>
      ) : null}

      {data.items.length === 0 ? (
        <ForecastsEmpty
          forecastsStatus={forecastsStatus}
          integrationsError={integrationsError}
        />
      ) : (
        <ul className="space-y-3">
          {data.items.map((fc) => (
            <li key={fc.id}>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      <ScoreBadge score={fc.score} />
                      <span className="ml-2">
                        {fc.agency ?? "Unknown agency"}
                        {fc.contracting_office ? ` · ${fc.contracting_office}` : ""}
                      </span>
                      {fc.matches_target_naics ? (
                        <span className="ml-2 rounded-sm bg-primary/10 px-1.5 py-0.5 font-semibold text-primary">
                          target NAICS
                        </span>
                      ) : null}
                    </p>
                    <h3 className="mt-1 text-sm font-semibold text-foreground">
                      {fc.title}
                    </h3>
                    {fc.description ? (
                      <p className="mt-2 text-sm leading-snug text-foreground">
                        {fc.description}
                      </p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      {fc.naics_code ? (
                        <span>
                          <NaicsBadge code={fc.naics_code} />
                        </span>
                      ) : null}
                      {fc.set_aside ? (
                        <span>
                          <TermPopover kind="set_aside" value="overview">Set-aside</TermPopover>
                          : {fc.set_aside}
                        </span>
                      ) : null}
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
                        <span className="text-warning">
                          <TermPopover kind="clause" value="RFP">RFP</TermPopover>{" "}
                          expected: {fmtDate(fc.expected_solicitation_date)}
                        </span>
                      ) : null}
                      {fc.incumbent_name ? (
                        <span>Incumbent: {fc.incumbent_name}</span>
                      ) : null}
                    </div>
                    {fc.poc_email || fc.poc_name ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        POC: {fc.poc_name ?? ""}
                        {fc.poc_name && fc.poc_email ? " · " : ""}
                        {fc.poc_email ? (
                          <a
                            href={`mailto:${fc.poc_email}`}
                            className="text-primary hover:underline"
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
                      className="text-muted-foreground hover:text-foreground"
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

/**
 * Standardized empty state. Teaches the layman what would normally render,
 * what would change that, and offers one CTA. The integration diagnostic
 * (worker run-status, manual trigger) is preserved as a fold-out admin
 * affordance — useful to the four founders, hidden by default for the
 * Phase 4+ external customer who shouldn't see internal scheduler details
 * at first glance.
 */
function ForecastsEmpty({
  forecastsStatus,
  integrationsError
}: {
  forecastsStatus: IntegrationsResponse["integrations"][number] | null;
  integrationsError: string | null;
}) {
  return (
    <div className="space-y-3">
      <EmptyState
        title="No agency forecasts in your lane right now."
        body={
          <>
            This page collects forecasts the agency has published 30–180 days
            before the matching SAM solicitation — your earliest signal that
            work is coming. Forecasts arrive once the daily Apify scrape
            (0500 ET) or the next ingestion sweep completes for your{" "}
            <TermPopover kind="naics" value="overview">NAICS</TermPopover>{" "}
            targets. If you set up your tenant in the last hour, the first
            run may still be in flight.
          </>
        }
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <LinkButton href="/forecasts?all=1" variant="primary">
              Show all NAICS forecasts
            </LinkButton>
            <LinkButton href="/settings" variant="secondary">
              Review NAICS targets
            </LinkButton>
          </div>
        }
      />
      <details className="rounded-md border border-border bg-secondary px-4 py-3">
        <summary className="cursor-pointer text-[11px] font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground">
          Admin diagnostic — worker run status
        </summary>
        <div className="mt-3">
          <IntegrationDiagnostic
            status={forecastsStatus}
            fetchError={integrationsError}
            triggerAction={async () => {
              "use server";
              await triggerForecastsRun();
            }}
          />
        </div>
      </details>
    </div>
  );
}
