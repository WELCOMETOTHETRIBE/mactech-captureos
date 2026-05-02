import type { WebMentionsResponse } from "@/lib/api";
import { refreshWebMentions } from "@/lib/web-mentions";

const KIND_LABEL: Record<string, string> = {
  program: "Program",
  incumbent: "Incumbent risk",
  press: "Industry press",
  agency_news: "Agency news",
};

/**
 * Web mentions card — extracted from the opp detail page in Sprint B.
 * Shows top Google results for the program, the incumbent, and recent
 * agency NAICS news. Surfaces only on the pursuit detail page now,
 * where a capture lead is doing the deep read.
 */
export function WebMentionsCard({
  opportunityId,
  mentions,
}: {
  opportunityId: string;
  mentions: WebMentionsResponse | null;
}) {
  const groups = mentions?.groups ?? [];
  const hasKey = mentions?.has_serpapi_key ?? false;
  return (
    <section className="rounded-md border border-paper-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-neutral-500">
            Web mentions
          </p>
          <h2 className="mt-1 text-base font-semibold text-neutral-900">
            What the open web says
          </h2>
          <p className="mt-1 text-xs text-neutral-500">
            Top Google results for this program, the incumbent (if known), and
            recent agency NAICS news. Cached 7 days; press refresh to re-bill.
          </p>
        </div>
        {hasKey ? (
          <form action={refreshWebMentions}>
            <input type="hidden" name="opportunity_id" value={opportunityId} />
            <button
              type="submit"
              className="rounded-md border border-brand-700 bg-brand-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-800"
            >
              {groups.length === 0 ? "Pull mentions" : "Refresh"}
            </button>
          </form>
        ) : (
          <span className="text-xs text-neutral-400">
            SERPAPI_KEY not configured
          </span>
        )}
      </div>

      {groups.length === 0 ? (
        <p className="mt-4 text-sm text-neutral-500">
          {hasKey
            ? "No mentions cached yet. Click Pull mentions to run a query."
            : "Set SERPAPI_KEY on the API service to enable this panel."}
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          {groups.map((g) => (
            <div
              key={g.kind}
              className="rounded-md border border-paper-200 bg-paper-50 p-3"
            >
              <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                {KIND_LABEL[g.kind] ?? g.kind}
                {g.is_stale ? (
                  <span className="ml-2 text-amber-700">stale</span>
                ) : null}
              </p>
              <p className="mt-1 truncate text-[11px] text-neutral-400">
                {g.query}
              </p>
              {g.results.length === 0 ? (
                <p className="mt-3 text-xs text-neutral-500">No results.</p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {g.results.slice(0, 5).map((r) => (
                    <li key={r.position}>
                      <a
                        href={r.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-brand-800 hover:underline"
                      >
                        {r.title}
                      </a>
                      {r.displayed_link ? (
                        <p className="text-[11px] text-neutral-500">
                          {r.displayed_link}
                          {r.date ? ` · ${r.date}` : ""}
                        </p>
                      ) : null}
                      {r.snippet ? (
                        <p className="mt-1 text-xs leading-snug text-neutral-700">
                          {r.snippet}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
