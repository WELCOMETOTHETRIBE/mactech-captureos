import Link from "next/link";
import { apiFetch, type AgencyEventsResponse } from "@/lib/api";
import { Card, EmptyState, LinkButton, PageHeader, fmtDate } from "@/components/ui";
import { TermPopover } from "@/components/term-popover";

export const dynamic = "force-dynamic";

const KIND_LABEL: Record<string, string> = {
  industry_day: "Industry day",
  pre_solicitation: "Pre-solicitation",
  meet_the_buyer: "Meet the buyer",
  symposium: "Symposium",
  conference: "Conference",
  webinar: "Webinar",
  other: "Other"
};

export default async function EventsPage() {
  const data = await apiFetch<AgencyEventsResponse>(
    "/events?upcoming_only=true&limit=100"
  ).catch(() => ({ total: 0, items: [] }) as AgencyEventsResponse);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Where to be"
        title="Industry days & pre-sol"
        subtitle={
          <span>
            Scraped daily from DoD{" "}
            <TermPopover kind="set_aside" value="osbp">OSBP</TermPopover>,
            NIWC, AFCEA, GSA OSDBU, DHS S&amp;T, AFLCMC, and Army OSBP.{" "}
            <TermPopover kind="event_kind" value="industry_day">
              Industry-day
            </TermPopover>{" "}
            attendance is the strongest predictor of bid/no-bid intel quality.
          </span>
        }
      />

      {data.items.length === 0 ? (
        <EventsEmpty />
      ) : (
        <ul className="space-y-3">
          {data.items.map((ev) => (
            <li key={ev.id}>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      {ev.kind ? (
                        <TermPopover kind="event_kind" value={ev.kind}>
                          {KIND_LABEL[ev.kind] ?? ev.kind}
                        </TermPopover>
                      ) : (
                        "Event"
                      )}
                      {ev.agency ? ` · ${ev.agency}` : ""}
                    </p>
                    <h3 className="mt-1 text-sm font-semibold text-foreground">
                      {ev.title}
                    </h3>
                    {ev.summary ? (
                      <p className="mt-2 text-sm leading-snug text-foreground">
                        {ev.summary}
                      </p>
                    ) : null}
                    <p className="mt-2 text-xs text-muted-foreground">
                      {ev.starts_at ? fmtDate(ev.starts_at) : "Date TBD"}
                      {ev.ends_at && ev.ends_at !== ev.starts_at
                        ? ` – ${fmtDate(ev.ends_at)}`
                        : ""}
                      {ev.location ? ` · ${ev.location}` : ""}
                    </p>
                    {ev.naics_codes.length > 0 ? (
                      <p className="mt-1 text-xs text-muted-foreground">
                        <TermPopover kind="naics" value="overview">NAICS</TermPopover>
                        : {ev.naics_codes.join(", ")}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-col items-end gap-2 text-xs">
                    {ev.registration_url ? (
                      <LinkButton
                        href={ev.registration_url}
                        external
                        variant="primary"
                        size="sm"
                      >
                        Register
                      </LinkButton>
                    ) : null}
                    <a
                      href={ev.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-foreground"
                    >
                      Source ({ev.source_host ?? "link"})
                    </a>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <p className="text-xs text-muted-foreground">
        Coverage gaps?{" "}
        <Link
          href="/library"
          className="text-primary hover:underline"
        >
          Add seed URLs in the library
        </Link>{" "}
        — the seed list ships with the daily 0500 ET scrape.
      </p>
    </div>
  );
}

/**
 * Layman-tone empty state. Teaches what the page would normally show, what
 * would change that, and offers one primary action. The previous version
 * sent the user to /forecasts to "check the diagnostic" — that's an ops
 * voice we want to keep behind a fold-out, not the first thing a layman
 * reads.
 */
function EventsEmpty() {
  return (
    <div className="space-y-3">
      <EmptyState
        title="No upcoming industry days on the radar."
        body={
          <>
            This page lists industry days, pre-solicitation events, and
            meet-the-buyer sessions where you can ask the program office
            real questions before the proposal window opens. The daily
            Apify scrape (0500 ET) refreshes from seven federal sources;
            check back in a day, or browse forecasts to see what work is
            coming.
          </>
        }
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <LinkButton href="/forecasts" variant="primary">
              Browse forecasts
            </LinkButton>
            <LinkButton href="/library" variant="secondary">
              Suggest a source
            </LinkButton>
          </div>
        }
      />
      <details className="rounded-md border border-border bg-secondary px-4 py-3">
        <summary className="cursor-pointer text-[11px] font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground">
          Admin diagnostic — event ingestion sources
        </summary>
        <div className="mt-3 text-xs text-muted-foreground">
          <p>
            Events are scraped daily at 0500 ET from DoD OSBP, NIWC, AFCEA,
            GSA OSDBU, DHS S&amp;T, AFLCMC, and Army OSBP. If this list
            stays empty for more than 24 hours, the worker run for the day
            may have failed — check the forecasts integration diagnostic on{" "}
            <Link
              href="/forecasts"
              className="text-primary hover:underline"
            >
              /forecasts
            </Link>
            {" "}for the most recent run.
          </p>
        </div>
      </details>
    </div>
  );
}
