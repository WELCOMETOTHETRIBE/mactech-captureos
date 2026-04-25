import Link from "next/link";
import { apiFetch, type OpportunityListResponse } from "@/lib/api";
import {
  Badge,
  EmptyState,
  NoticeTypeBadge,
  PageHeader,
  ScoreBadge,
  SetAsideBadge,
  fmtDate,
  fmtRelativeDays
} from "@/components/ui";

export const dynamic = "force-dynamic";

type SP = Promise<{
  page?: string;
  q?: string;
  naics_code?: string;
  set_aside?: string;
  notice_type?: string;
  agency?: string;
  assigned_founder?: string;
  score_min?: string;
  score_max?: string;
  sort?: string;
}>;

const SORT_LABELS: Record<string, string> = {
  score_desc: "Score (high → low)",
  posted_desc: "Newest posted",
  deadline_asc: "Deadline (soonest first)"
};

export default async function OpportunitiesListPage({
  searchParams
}: {
  searchParams: SP;
}) {
  const sp = await searchParams;
  const params = new URLSearchParams();
  const limit = 25;
  const page = Math.max(1, parseInt(sp.page ?? "1", 10) || 1);
  const sort = sp.sort ?? "score_desc";
  const score_min = sp.score_min ?? "0";
  const score_max = sp.score_max ?? "100";

  params.set("page", String(page));
  params.set("limit", String(limit));
  params.set("sort", sort);
  params.set("score_min", score_min);
  params.set("score_max", score_max);
  if (sp.q) params.set("q", sp.q);
  if (sp.naics_code) params.set("naics_code", sp.naics_code);
  if (sp.set_aside) params.set("set_aside", sp.set_aside);
  if (sp.notice_type) params.set("notice_type", sp.notice_type);
  if (sp.agency) params.set("agency", sp.agency);
  if (sp.assigned_founder) params.set("assigned_founder", sp.assigned_founder);

  const data = await apiFetch<OpportunityListResponse>(
    `/opportunities?${params.toString()}`
  );

  const start = data.items.length === 0 ? 0 : (data.page - 1) * data.limit + 1;
  const end = Math.min(start + data.items.length - 1, data.total);
  const activeFilters: string[] = [];
  if (sp.q) activeFilters.push(`q="${sp.q}"`);
  if (sp.naics_code) activeFilters.push(`NAICS ${sp.naics_code}`);
  if (sp.set_aside) activeFilters.push(sp.set_aside);
  if (sp.notice_type) activeFilters.push(sp.notice_type);
  if (sp.agency) activeFilters.push(`agency~"${sp.agency}"`);
  if (sp.assigned_founder) activeFilters.push(`@${sp.assigned_founder}`);
  if (score_min !== "0" || score_max !== "100")
    activeFilters.push(`score ${score_min}–${score_max}`);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="MacTech feed"
        title="Opportunities"
        subtitle={`Showing ${start}–${end} of ${data.total.toLocaleString()} ingested federal opportunities${activeFilters.length ? " — " + activeFilters.join(" · ") : ""}.`}
        trailing={
          activeFilters.length > 0 ? (
            <Link
              href="/opportunities"
              className="rounded-md border border-neutral-300 px-3 py-2 text-xs hover:border-neutral-500"
            >
              Clear filters
            </Link>
          ) : null
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        {/* Filters sidebar */}
        <aside className="space-y-4 lg:col-span-1">
          <FilterCard title="Search">
            <form action="/opportunities" method="GET" className="space-y-2">
              <input type="hidden" name="sort" value={sort} />
              {Object.entries(sp).map(([k, v]) =>
                k === "q" || k === "page" ? null : (
                  <input key={k} type="hidden" name={k} value={String(v ?? "")} />
                )
              )}
              <input
                name="q"
                defaultValue={sp.q ?? ""}
                placeholder="Title contains…"
                className="w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm focus:border-neutral-500 focus:outline-none"
              />
              <button
                type="submit"
                className="w-full rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
              >
                Search
              </button>
            </form>
          </FilterCard>

          <FilterCard title="Sort">
            <ul className="space-y-1 text-sm">
              {Object.entries(SORT_LABELS).map(([k, label]) => {
                const qs = new URLSearchParams(params);
                qs.set("sort", k);
                qs.delete("page");
                const active = sort === k;
                return (
                  <li key={k}>
                    <Link
                      href={`/opportunities?${qs.toString()}`}
                      className={
                        active
                          ? "block rounded-sm bg-neutral-900 px-2 py-1 text-white"
                          : "block rounded-sm px-2 py-1 hover:bg-neutral-100"
                      }
                    >
                      {label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </FilterCard>

          <FilterCard title="Score threshold">
            <div className="text-xs text-neutral-600">
              Currently: <span className="font-medium">{score_min}</span> –{" "}
              <span className="font-medium">{score_max}</span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {[
                { l: "Top (≥80)", min: "80", max: "100" },
                { l: "Digest (≥60)", min: "60", max: "100" },
                { l: "Med (40–59)", min: "40", max: "59" },
                { l: "All", min: "0", max: "100" }
              ].map((bucket) => {
                const qs = new URLSearchParams(params);
                qs.set("score_min", bucket.min);
                qs.set("score_max", bucket.max);
                qs.delete("page");
                const active =
                  score_min === bucket.min && score_max === bucket.max;
                return (
                  <Link
                    key={bucket.l}
                    href={`/opportunities?${qs.toString()}`}
                    className={`rounded-md border px-2 py-1 text-center text-[11px] ${
                      active
                        ? "border-neutral-900 bg-neutral-900 text-white"
                        : "border-neutral-300 hover:border-neutral-500"
                    }`}
                  >
                    {bucket.l}
                  </Link>
                );
              })}
            </div>
          </FilterCard>

          <FacetFilter
            title="Set-aside"
            paramKey="set_aside"
            facets={data.facets.set_asides}
            current={sp.set_aside ?? null}
            allParams={params}
            renderLabel={(k) => k}
          />

          <FacetFilter
            title="Notice type"
            paramKey="notice_type"
            facets={data.facets.notice_types}
            current={sp.notice_type ?? null}
            allParams={params}
            renderLabel={(k) => k}
          />

          <FacetFilter
            title="NAICS"
            paramKey="naics_code"
            facets={data.facets.naics}
            current={sp.naics_code ?? null}
            allParams={params}
            renderLabel={(k) => `NAICS ${k}`}
            limit={15}
          />

          <FacetFilter
            title="Assigned founder (≥60)"
            paramKey="assigned_founder"
            facets={data.facets.assigned_founder}
            current={sp.assigned_founder ?? null}
            allParams={params}
            renderLabel={(k) => k}
          />
        </aside>

        {/* Results list */}
        <div className="space-y-3 lg:col-span-3">
          {data.items.length === 0 ? (
            <EmptyState
              title="No opportunities match those filters."
              body="Try clearing one of them, lowering the score threshold, or expanding the date window."
              action={
                <Link
                  href="/opportunities"
                  className="text-sm text-blue-700 hover:underline"
                >
                  Clear filters
                </Link>
              }
            />
          ) : (
            <ul className="space-y-3">
              {data.items.map((opp) => (
                <li key={opp.id}>
                  <Link
                    href={`/opportunities/${opp.id}`}
                    className="block rounded-md border border-neutral-200 bg-white p-4 transition-colors hover:border-neutral-400"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <ScoreBadge score={opp.score} />
                      <NoticeTypeBadge type={opp.notice_type} />
                      <SetAsideBadge code={opp.set_aside} />
                      {opp.naics_code && (
                        <Badge tone="neutral">NAICS {opp.naics_code}</Badge>
                      )}
                      {opp.assigned_founder_slug && (
                        <Badge tone="violet">@{opp.assigned_founder_slug}</Badge>
                      )}
                      <span className="ml-auto text-[11px] text-neutral-500">
                        {fmtDate(opp.posted_at)}
                      </span>
                    </div>
                    <h3 className="mt-2 text-sm font-semibold leading-snug text-neutral-900">
                      {opp.title}
                    </h3>
                    {opp.agency_short && (
                      <p className="mt-1 text-[11px] text-neutral-500">
                        {opp.agency_short}
                      </p>
                    )}
                    {opp.why_it_matters && (
                      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-neutral-600">
                        {opp.why_it_matters}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-x-4 text-[11px] text-neutral-500">
                      {opp.incumbent_summary && (
                        <span>Incumbent: {opp.incumbent_summary}</span>
                      )}
                      {opp.response_deadline && (
                        <span>
                          Deadline:{" "}
                          {fmtRelativeDays(
                            opp.response_deadline,
                            opp.days_until_deadline
                          )}
                        </span>
                      )}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {/* Pagination */}
          {data.total > limit && (
            <Pagination
              page={data.page}
              limit={data.limit}
              total={data.total}
              hasNext={data.has_next}
              params={params}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function FilterCard({
  title,
  children
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-neutral-200 bg-white p-4">
      <p className="text-[11px] uppercase tracking-wider text-neutral-500">
        {title}
      </p>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function FacetFilter({
  title,
  paramKey,
  facets,
  current,
  allParams,
  renderLabel,
  limit = 10
}: {
  title: string;
  paramKey: string;
  facets: Record<string, number>;
  current: string | null;
  allParams: URLSearchParams;
  renderLabel: (k: string) => string;
  limit?: number;
}) {
  const entries = Object.entries(facets).slice(0, limit);
  return (
    <FilterCard title={title}>
      <ul className="space-y-1 text-sm">
        {current && (
          <li>
            <Link
              href={`/opportunities?${dropParam(allParams, paramKey).toString()}`}
              className="block rounded-sm bg-amber-50 px-2 py-1 text-[11px] text-amber-800 hover:bg-amber-100"
            >
              ✕ Clear {title.toLowerCase()}
            </Link>
          </li>
        )}
        {entries.map(([k, n]) => {
          const qs = new URLSearchParams(allParams);
          qs.set(paramKey, k);
          qs.delete("page");
          const active = current === k;
          return (
            <li key={k}>
              <Link
                href={`/opportunities?${qs.toString()}`}
                className={`flex items-center justify-between rounded-sm px-2 py-1 text-xs ${
                  active
                    ? "bg-neutral-900 text-white"
                    : "hover:bg-neutral-100 text-neutral-700"
                }`}
              >
                <span className="truncate">{renderLabel(k)}</span>
                <span className="ml-2 tabular-nums text-[10px] opacity-70">
                  {n}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </FilterCard>
  );
}

function dropParam(p: URLSearchParams, key: string): URLSearchParams {
  const out = new URLSearchParams(p);
  out.delete(key);
  out.delete("page");
  return out;
}

function Pagination({
  page,
  limit,
  total,
  hasNext,
  params
}: {
  page: number;
  limit: number;
  total: number;
  hasNext: boolean;
  params: URLSearchParams;
}) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const prev = new URLSearchParams(params);
  prev.set("page", String(Math.max(1, page - 1)));
  const next = new URLSearchParams(params);
  next.set("page", String(page + 1));
  return (
    <nav className="flex items-center justify-between rounded-md border border-neutral-200 bg-white p-3 text-xs">
      <span className="text-neutral-500">
        Page {page} of {totalPages.toLocaleString()}
      </span>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link
            href={`/opportunities?${prev.toString()}`}
            className="rounded-md border border-neutral-300 px-2 py-1 hover:border-neutral-500"
          >
            ← Prev
          </Link>
        ) : (
          <span className="rounded-md border border-neutral-200 px-2 py-1 text-neutral-300">
            ← Prev
          </span>
        )}
        {hasNext ? (
          <Link
            href={`/opportunities?${next.toString()}`}
            className="rounded-md border border-neutral-300 px-2 py-1 hover:border-neutral-500"
          >
            Next →
          </Link>
        ) : (
          <span className="rounded-md border border-neutral-200 px-2 py-1 text-neutral-300">
            Next →
          </span>
        )}
      </div>
    </nav>
  );
}
