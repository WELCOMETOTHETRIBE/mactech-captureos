import Link from "next/link";
import { apiFetch, type AgencyEventsResponse } from "@/lib/api";
import { Card, PageHeader, fmtDate } from "@/components/ui";

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
            Scraped daily from DoD OSBP, NIWC, AFCEA, GSA OSDBU, DHS S&amp;T,
            AFLCMC, and Army OSBP. Industry-day attendance is the strongest
            predictor of bid/no-bid intel quality.
          </span>
        }
      />

      {data.items.length === 0 ? (
        <Card>
          <p className="text-sm text-neutral-500">
            No upcoming events captured yet. The Apify daily beat (0500 ET)
            populates this on completion. If this stays empty after 24
            hours, check that <code>APIFY_API_TOKEN</code> and the
            actor-level webhook are configured.
          </p>
        </Card>
      ) : (
        <ul className="space-y-3">
          {data.items.map((ev) => (
            <li key={ev.id}>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                      {ev.kind ? KIND_LABEL[ev.kind] ?? ev.kind : "Event"}
                      {ev.agency ? ` · ${ev.agency}` : ""}
                    </p>
                    <h3 className="mt-1 text-sm font-semibold text-neutral-900">
                      {ev.title}
                    </h3>
                    {ev.summary ? (
                      <p className="mt-2 text-sm leading-snug text-neutral-700">
                        {ev.summary}
                      </p>
                    ) : null}
                    <p className="mt-2 text-xs text-neutral-500">
                      {ev.starts_at ? fmtDate(ev.starts_at) : "Date TBD"}
                      {ev.ends_at && ev.ends_at !== ev.starts_at
                        ? ` – ${fmtDate(ev.ends_at)}`
                        : ""}
                      {ev.location ? ` · ${ev.location}` : ""}
                    </p>
                    {ev.naics_codes.length > 0 ? (
                      <p className="mt-1 text-xs text-neutral-500">
                        NAICS: {ev.naics_codes.join(", ")}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-col items-end gap-2 text-xs">
                    {ev.registration_url ? (
                      <a
                        href={ev.registration_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-md border border-brand-700 bg-brand-700 px-3 py-1.5 font-medium text-white hover:bg-brand-800"
                      >
                        Register
                      </a>
                    ) : null}
                    <a
                      href={ev.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-neutral-500 hover:text-neutral-800"
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

      <p className="text-xs text-neutral-500">
        Coverage gaps?{" "}
        <Link
          href="/library"
          className="text-brand-700 hover:underline"
        >
          Add seed URLs in the library
        </Link>{" "}
        — the seed list is configured in
        <code className="ml-1 rounded bg-neutral-100 px-1">
          mactech_workers.tasks.apify_industry_days
        </code>
        for now.
      </p>
    </div>
  );
}
