import Link from "next/link";
import { apiFetch, type ForecastsResponse, type MeResponse } from "@/lib/api";
import {
  Badge,
  Card,
  EmptyState,
  LinkButton,
  NaicsBadge,
  PageHeader,
  Pillar,
  ScoreBadge,
  fmtDate,
  fmtMoney
} from "@/components/ui";
import { TermPopover } from "@/components/term-popover";

export const dynamic = "force-dynamic";

type SP = {
  all?: string;
  agency?: string;
  set_aside?: string;
  pop?: string;
  founder?: string;
  mine?: string;
};

const POP_WINDOW_LABEL: Record<string, string> = {
  "6": "Next 6 months",
  "12": "Next 12 months",
  "24": "Next 24 months"
};

export default async function RecompetesPage({
  searchParams
}: {
  searchParams?: Promise<SP>;
}) {
  const sp = (await searchParams) ?? {};
  const showAll = sp.all === "1";
  const agency = sp.agency ?? "";
  const setAsideScope = sp.set_aside ?? "all";
  const popWindow = sp.pop ?? "";
  const founderSlug = sp.founder ?? "";
  const mineOnly = sp.mine === "1";

  const params = new URLSearchParams({
    naics_filter: showAll ? "false" : "true",
    set_aside_scope: setAsideScope,
    limit: "200"
  });
  if (agency) params.set("agency", agency);
  if (popWindow) params.set("pop_window_months", popWindow);
  if (founderSlug) params.set("assigned_founder", founderSlug);
  if (mineOnly) params.set("mine_only", "true");

  const [data, me] = await Promise.all([
    apiFetch<ForecastsResponse>(`/recompetes?${params.toString()}`).catch(
      () =>
        ({
          total: 0,
          items: [],
          target_naics_filter: false,
          target_naics: []
        }) as ForecastsResponse
    ),
    apiFetch<MeResponse>("/me").catch(() => null as MeResponse | null)
  ]);

  const myFounder = me?.founder?.slug ?? null;
  const myFounderName = me?.founder?.full_name ?? null;

  // Filter chip helpers — keep existing params, toggle the one being changed.
  const buildHref = (overrides: Partial<SP>) => {
    const next = new URLSearchParams();
    const merged: SP = {
      all: showAll ? "1" : undefined,
      agency: agency || undefined,
      set_aside: setAsideScope !== "all" ? setAsideScope : undefined,
      pop: popWindow || undefined,
      founder: founderSlug || undefined,
      mine: mineOnly ? "1" : undefined,
      ...overrides
    };
    Object.entries(merged).forEach(([k, v]) => {
      if (v !== undefined && v !== "") next.set(k, String(v));
    });
    const q = next.toString();
    return q ? `/recompetes?${q}` : "/recompetes";
  };

  const chipClass = (active: boolean) =>
    active
      ? "rounded-full border border-primary bg-primary px-3 py-1 text-xs font-medium text-primary-foreground"
      : "rounded-full border border-border px-3 py-1 text-xs text-foreground hover:border-foreground/40";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Recompete radar"
        title="Forecasts with named incumbents"
        subtitle={
          <span>
            Every forecast where we know who currently holds the contract.
            Sorted by fit score for your{" "}
            <TermPopover kind="naics" value="overview">NAICS</TermPopover>{" "}
            profile, urgency boosted by{" "}
            <TermPopover kind="pop" value="overview">POP</TermPopover>-end
            proximity. Filter by agency,{" "}
            <TermPopover kind="set_aside" value="overview">set-aside</TermPopover>{" "}
            scope, or POP window to focus on what matters this quarter.
          </span>
        }
      />

      {/* Filter strip */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-[11px] uppercase tracking-wider text-muted-foreground">
          <TermPopover kind="set_aside" value="overview">Set-aside</TermPopover>:
        </span>
        <Link href={buildHref({ set_aside: undefined })} className={chipClass(setAsideScope === "all")}>
          All
        </Link>
        <Link href={buildHref({ set_aside: "sdvosb" })} className={chipClass(setAsideScope === "sdvosb")}>
          SDVOSB only
        </Link>
        <Link href={buildHref({ set_aside: "sb" })} className={chipClass(setAsideScope === "sb")}>
          Small biz
        </Link>

        <span className="ml-3 mr-1 text-[11px] uppercase tracking-wider text-muted-foreground">
          Agency:
        </span>
        <Link href={buildHref({ agency: undefined })} className={chipClass(!agency)}>
          All
        </Link>
        <Link href={buildHref({ agency: "DHS" })} className={chipClass(agency === "DHS")}>
          DHS
        </Link>
        <Link href={buildHref({ agency: "DOE" })} className={chipClass(agency === "DOE")}>
          DOE
        </Link>

        <span className="ml-3 mr-1 text-[11px] uppercase tracking-wider text-muted-foreground">
          <TermPopover kind="pop" value="overview">POP</TermPopover> ends:
        </span>
        <Link href={buildHref({ pop: undefined })} className={chipClass(!popWindow)}>
          Any time
        </Link>
        {Object.entries(POP_WINDOW_LABEL).map(([k, label]) => (
          <Link key={k} href={buildHref({ pop: k })} className={chipClass(popWindow === k)}>
            {label}
          </Link>
        ))}

        {myFounder ? (
          <>
            <span className="ml-3 mr-1 text-[11px] uppercase tracking-wider text-muted-foreground">
              Lane:
            </span>
            <Link
              href={buildHref({ mine: undefined, founder: undefined })}
              className={chipClass(!mineOnly && !founderSlug)}
            >
              Any founder
            </Link>
            <Link
              href={buildHref({ mine: "1", founder: undefined })}
              className={chipClass(mineOnly)}
            >
              Mine ({myFounderName?.split(" ")[0]})
            </Link>
          </>
        ) : null}
      </div>

      {/* Results */}
      {data.target_naics_filter ? (
        <div className="text-xs text-muted-foreground">
          Filtered to your {data.target_naics.length} target NAICS.{" "}
          <Link href={buildHref({ all: "1" })} className="text-primary hover:underline">
            Show all NAICS
          </Link>
        </div>
      ) : data.target_naics.length > 0 ? (
        <div className="text-xs text-muted-foreground">
          Showing all NAICS.{" "}
          <Link href={buildHref({ all: undefined })} className="text-primary hover:underline">
            Filter to your NAICS
          </Link>
        </div>
      ) : null}

      <p className="text-xs text-muted-foreground">
        {data.items.length} recompete{data.items.length === 1 ? "" : "s"}.
      </p>

      {data.items.length === 0 ? (
        <EmptyState
          title="No recompetes match those filters."
          body={
            <>
              Recompetes are forecasts where the agency named the current
              incumbent — the strongest signal that the work will repeat.
              Try widening the set-aside scope, agency, or POP window above.
            </>
          }
          action={
            <div className="flex justify-center gap-2">
              <LinkButton href="/recompetes" variant="primary">
                Clear filters
              </LinkButton>
              <LinkButton href="/forecasts" variant="secondary">
                Browse all forecasts
              </LinkButton>
            </div>
          }
        />
      ) : (
        <ul className="space-y-3">
          {data.items.map((fc) => (
            <li key={fc.id}>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wider text-muted-foreground">
                      <ScoreBadge score={fc.score} />
                      <span>
                        {fc.agency ?? "Unknown agency"}
                        {fc.contracting_office
                          ? ` · ${fc.contracting_office}`
                          : ""}
                      </span>
                      {fc.assigned_founder_pillar ? (
                        <Pillar pillar={fc.assigned_founder_pillar} />
                      ) : null}
                      {fc.assigned_founder_name ? (
                        <span className="text-foreground">
                          @{fc.assigned_founder_name.split(" ")[0]}
                        </span>
                      ) : null}
                      {fc.matches_target_naics ? (
                        <span className="rounded-sm bg-primary/10 px-1.5 py-0.5 font-semibold text-primary">
                          target NAICS
                        </span>
                      ) : null}
                    </p>
                    <h3 className="mt-1 text-sm font-semibold text-foreground">
                      {fc.title}
                    </h3>
                    {fc.description ? (
                      <p className="mt-2 line-clamp-2 text-sm leading-snug text-foreground">
                        {fc.description}
                      </p>
                    ) : null}
                    <div className="mt-2 rounded-md bg-warning/10 px-3 py-2 text-xs text-warning">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <strong>Incumbent:</strong> {fc.incumbent_name}
                        {fc.incumbent_sec_ticker ? (
                          <TermPopover
                            kind="incumbent_distress"
                            value="sec_ticker"
                          >
                            <span className="rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[10px] text-foreground">
                              {fc.incumbent_sec_ticker}
                            </span>
                          </TermPopover>
                        ) : null}
                        {fc.incumbent_distress_score !== null &&
                        fc.incumbent_distress_score > 0 ? (
                          <Badge tone="red">
                            <TermPopover
                              kind="incumbent_distress"
                              value="score"
                            >
                              distress signal {fc.incumbent_distress_score}
                            </TermPopover>
                          </Badge>
                        ) : null}
                      </div>
                      {fc.incumbent_contract_number ? (
                        <div className="mt-1 text-[11px]">
                          Contract {fc.incumbent_contract_number}
                          {fc.period_of_performance_end ? (
                            <span className="ml-2">
                              <TermPopover kind="pop" value="overview">POP</TermPopover>{" "}
                              ends {fmtDate(fc.period_of_performance_end)}
                            </span>
                          ) : null}
                        </div>
                      ) : fc.period_of_performance_end ? (
                        <div className="mt-1 text-[11px]">
                          <TermPopover kind="pop" value="overview">POP</TermPopover>{" "}
                          ends {fmtDate(fc.period_of_performance_end)}
                        </div>
                      ) : null}
                      {fc.incumbent_total_obligations !== null &&
                      fc.incumbent_total_obligations > 0 ? (
                        <div className="mt-1 text-[11px]">
                          Federal footprint:{" "}
                          {fmtMoney(fc.incumbent_total_obligations)} across{" "}
                          {fc.incumbent_award_count ?? 0} awards (USASpending)
                        </div>
                      ) : null}
                      {fc.incumbent_distress_summary ? (
                        <div className="mt-1 text-[11px]">
                          <TermPopover
                            kind="incumbent_distress"
                            value="edgar"
                          >
                            SEC EDGAR
                          </TermPopover>
                          : {fc.incumbent_distress_summary}
                        </div>
                      ) : fc.incumbent_filings_last_90d !== null &&
                        fc.incumbent_filings_last_90d > 0 ? (
                        <div className="mt-1 text-[11px]">
                          <TermPopover
                            kind="incumbent_distress"
                            value="edgar"
                          >
                            SEC EDGAR
                          </TermPopover>
                          : {fc.incumbent_filings_last_90d} filing
                          {fc.incumbent_filings_last_90d !== 1 ? "s" : ""} in
                          last 90 days
                        </div>
                      ) : null}
                    </div>
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
                      {fc.contract_type ? (
                        <span>Type: {fc.contract_type}</span>
                      ) : null}
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
