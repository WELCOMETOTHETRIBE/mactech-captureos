import Link from "next/link";
import { apiFetch, type OpportunityListResponse } from "@/lib/api";
import {
  Badge,
  EmptyState,
  HpewBadge,
  NaicsBadge,
  NoticeTypeBadge,
  PageHeader,
  ScoreBadge,
  SetAsideBadge,
  fmtDate,
  fmtRelativeDays
} from "@/components/ui";
import { KeyboardList } from "@/components/keyboard-list";

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
  sweet_spot_only?: string;
  high_moat_min?: string;
}>;

const SORT_LABELS: Record<string, string> = {
  score_desc: "Score (high → low)",
  high_moat_desc: "High-moat (sweet spots first)",
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
  // Sweet-spot toggle forces the high-moat sort so the gold rail sits
  // at the top of the page. Otherwise honor whatever ?sort= the user
  // selected, defaulting to general score.
  const sweetSpotOnly = sp.sweet_spot_only === "true";
  const sort = sweetSpotOnly ? "high_moat_desc" : sp.sort ?? "score_desc";
  const score_min = sp.score_min ?? "0";
  const score_max = sp.score_max ?? "100";

  params.set("page", String(page));
  params.set("limit", String(limit));
  params.set("sort", sort);
  params.set("score_min", score_min);
  params.set("score_max", score_max);
  if (sweetSpotOnly) params.set("sweet_spot_only", "true");
  if (sp.high_moat_min) params.set("high_moat_min", sp.high_moat_min);
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
  if (sweetSpotOnly) activeFilters.push("sweet spots only");

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

      {/* Quick filter bar — score buckets + sweet-spot toggle as a
          horizontal segmented control. The sweet-spot pill is the
          fourth option (after the three score buckets) and forces
          ?sort=high_moat_desc so the gold rail rises to the top. */}
      <div className="rounded-lg border border-neutral-200 bg-white p-3">
        <div className="flex flex-wrap items-center gap-3">
          <p
            className="text-xs font-medium uppercase tracking-wide text-neutral-500"
            title="≥80 = pursue now. 60–79 = worth a look. 40–59 = watch list. <40 = long shot. Sweet spots = high-probability easy wins from the parallel high-moat track."
          >
            Score
          </p>
          <div
            role="group"
            aria-label="Score filter"
            className="flex gap-1"
          >
            {[
              { l: "Top fit", min: "80", max: "100" },
              { l: "Worth a look", min: "60", max: "100" },
              { l: "Watch list", min: "40", max: "59" },
              { l: "All", min: "0", max: "100" }
            ].map((bucket) => {
              const qs = new URLSearchParams(params);
              qs.set("score_min", bucket.min);
              qs.set("score_max", bucket.max);
              qs.delete("sweet_spot_only");
              qs.delete("page");
              const active =
                !sweetSpotOnly &&
                score_min === bucket.min &&
                score_max === bucket.max;
              return (
                <Link
                  key={bucket.l}
                  href={`/opportunities?${qs.toString()}`}
                  aria-pressed={active}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    active
                      ? "bg-brand-700 text-white"
                      : "border border-neutral-300 text-neutral-700 hover:border-neutral-500"
                  }`}
                >
                  {bucket.l}
                </Link>
              );
            })}
            {/* Sweet-spot toggle — federal-procurement gold border + ink.
                No fill (per brief §11 Q3 — gold reads as gravitas, not
                bling). Forces high_moat_desc sort + sweet_spot_only=true. */}
            {(() => {
              const qs = new URLSearchParams(params);
              qs.set("sweet_spot_only", "true");
              qs.set("sort", "high_moat_desc");
              qs.set("score_min", "0");
              qs.set("score_max", "100");
              qs.delete("page");
              return (
                <Link
                  href={`/opportunities?${qs.toString()}`}
                  aria-pressed={sweetSpotOnly}
                  title="High-Probability Easy Wins: opps matching MacTech's strongest win profile (UFGS 25 / FRCS cyber, set-aside fit, thin interested-vendors list)."
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors border-2 ${
                    sweetSpotOnly
                      ? "border-[hsl(var(--high-moat))] text-[hsl(var(--high-moat))]"
                      : "border-[hsl(var(--high-moat))]/30 text-[hsl(var(--high-moat))] hover:border-[hsl(var(--high-moat))]/60"
                  }`}
                >
                  Sweet spots
                </Link>
              );
            })()}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <form action="/opportunities" method="GET" className="flex gap-1">
              <input type="hidden" name="sort" value={sort} />
              {Object.entries(sp).map(([k, v]) =>
                k === "q" || k === "page" ? null : (
                  <input key={k} type="hidden" name={k} value={String(v ?? "")} />
                )
              )}
              <input
                name="q"
                defaultValue={sp.q ?? ""}
                placeholder="Search title…"
                className="w-48 rounded-md border border-neutral-300 px-2 py-1.5 text-xs focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              <button
                type="submit"
                className="rounded-md border border-neutral-300 px-2 py-1.5 text-xs hover:border-neutral-500"
              >
                Search
              </button>
            </form>
            <span
              className="rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1.5 text-xs text-neutral-600"
              title="Sort order. Change it from the More filters drawer."
            >
              Sort: {SORT_LABELS[sort] ?? sort}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        {/* Filters sidebar */}
        <aside className="space-y-4 lg:col-span-1">
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
            title="Assigned founder (≥60)"
            paramKey="assigned_founder"
            facets={data.facets.assigned_founder}
            current={sp.assigned_founder ?? null}
            allParams={params}
            renderLabel={(k) => k}
          />

          <details className="rounded-lg border border-neutral-200 bg-white">
            <summary className="cursor-pointer rounded-lg px-4 py-3 text-xs font-medium uppercase tracking-wide text-neutral-700 hover:bg-neutral-50">
              More filters
            </summary>
            <div className="space-y-4 px-4 pb-4">
              <FacetFilter
                title="NAICS"
                paramKey="naics_code"
                facets={data.facets.naics}
                current={sp.naics_code ?? null}
                allParams={params}
                renderLabel={(k) => `NAICS ${k}`}
                limit={15}
              />

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
                              ? "block rounded-sm bg-brand-700 px-2 py-1 text-xs text-white"
                              : "block rounded-sm px-2 py-1 text-xs hover:bg-neutral-100"
                          }
                        >
                          {label}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </FilterCard>
            </div>
          </details>
        </aside>

        {/* Results list */}
        <div className="space-y-3 lg:col-span-3">
          {data.items.length === 0 ? (
            <EmptyState
              title={
                activeFilters.length > 0
                  ? "No opportunities match those filters."
                  : "No opportunities have landed yet."
              }
              body={
                activeFilters.length > 0 ? (
                  <>
                    Active filters:{" "}
                    <span className="font-mono text-[11px]">
                      {activeFilters.join(" · ")}
                    </span>
                    . Try clearing one, lowering the score threshold, or
                    expanding the date window.
                  </>
                ) : (
                  <>
                    SAM.gov ingestion runs every 2h and scoring every 20m.
                    The first feed for a brand-new tenant takes 3–10 minutes
                    after onboarding completes. If you finished setup
                    recently, give it a few minutes and refresh.
                  </>
                )
              }
              action={
                activeFilters.length > 0 ? (
                  <div className="flex flex-wrap justify-center gap-2">
                    <Link
                      href="/opportunities"
                      className="rounded-md border border-brand-700 bg-brand-700 px-3 py-2 text-sm font-medium text-white hover:bg-brand-800"
                    >
                      Clear all filters
                    </Link>
                    {(score_min !== "0" || score_max !== "100") && (
                      <Link
                        href={`/opportunities?${(() => {
                          const p = new URLSearchParams(params);
                          p.delete("score_min");
                          p.delete("score_max");
                          p.delete("page");
                          return p.toString();
                        })()}`}
                        className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-800 hover:border-neutral-500"
                      >
                        Clear score filter
                      </Link>
                    )}
                  </div>
                ) : (
                  <Link
                    href="/dashboard"
                    className="rounded-md border border-brand-700 bg-brand-700 px-3 py-2 text-sm font-medium text-white hover:bg-brand-800"
                  >
                    Back to dashboard
                  </Link>
                )
              }
            />
          ) : (
            <KeyboardList>
            <ul className="space-y-3">
              {data.items.map((opp) => {
                // Pick ONE contextual chip beyond the score, in priority order.
                // Sources Sought is the most actionable; set-aside next; NAICS last.
                const noticeIsSourcesSought = (opp.notice_type ?? "")
                  .toLowerCase()
                  .includes("sources sought");
                // Sweet-spot row treatment: gold left border + HPEW chip.
                // No background fill, no shadow on hover (calmer leaderboard
                // posture per brief §6 motion guidance).
                const rowClass = opp.is_sweet_spot
                  ? "group block rounded-lg border border-neutral-200 border-l-[3px] border-l-[hsl(var(--high-moat))] bg-white p-5 transition-colors hover:border-brand-300 hover:border-l-[hsl(var(--high-moat))]"
                  : "group block rounded-lg border border-neutral-200 bg-white p-5 transition-colors hover:border-brand-300 hover:shadow-sm";
                // Title promotion: Claude-generated scope_one_sentence
                // (from the post-score worker chain) reads as a clean
                // human-language title. Fall back to the raw SAM title
                // when the brief isn't generated yet (score < 60, or
                // ingest <20min ago).
                const primaryTitle = opp.scope_one_sentence ?? opp.title;
                const hasPromotedTitle = !!opp.scope_one_sentence;
                return (
                  <li key={opp.id}>
                    <Link
                      href={`/opportunities/${opp.id}`}
                      data-kb-row
                      className={rowClass}
                      title={
                        hasPromotedTitle
                          ? `SAM title: ${opp.title}`
                          : undefined
                      }
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <ScoreBadge score={opp.score} size="lg" />
                            {opp.is_sweet_spot && <HpewBadge />}
                            {noticeIsSourcesSought && (
                              <NoticeTypeBadge type={opp.notice_type} />
                            )}
                            {!noticeIsSourcesSought && opp.set_aside && (
                              <SetAsideBadge code={opp.set_aside} />
                            )}
                            {opp.assigned_founder_slug && (
                              <Badge
                                tone="brand"
                                title={`Assigned to @${opp.assigned_founder_slug}`}
                              >
                                @{opp.assigned_founder_slug}
                              </Badge>
                            )}
                            {/* Hidden-by-default chips, revealed on hover */}
                            <span className="hidden gap-2 group-hover:inline-flex">
                              {!noticeIsSourcesSought && (
                                <NoticeTypeBadge type={opp.notice_type} />
                              )}
                              {noticeIsSourcesSought && opp.set_aside && (
                                <SetAsideBadge code={opp.set_aside} />
                              )}
                              <NaicsBadge code={opp.naics_code} />
                            </span>
                          </div>
                          <h3 className="mt-3 line-clamp-2 text-[15px] font-semibold leading-snug text-neutral-900">
                            {primaryTitle}
                          </h3>
                          {/* When we promoted the brief sentence, show the
                              raw SAM title as a muted second line so a BD
                              lead can verify provenance at a glance. */}
                          {hasPromotedTitle && (
                            <p className="mt-1 line-clamp-1 text-xs text-neutral-500">
                              <span className="uppercase tracking-wider text-neutral-400">
                                SAM:
                              </span>{" "}
                              {opp.title}
                            </p>
                          )}
                          {opp.agency_short && (
                            <p className="mt-1 text-sm text-neutral-500">
                              {opp.agency_short}
                            </p>
                          )}
                          {opp.why_it_matters && (
                            <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-neutral-600">
                              {opp.why_it_matters}
                            </p>
                          )}
                          {opp.incumbent_summary && (
                            <p className="mt-2 text-xs text-neutral-500">
                              Incumbent: {opp.incumbent_summary}
                            </p>
                          )}
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="text-[11px] uppercase tracking-wide text-neutral-500">
                            Deadline
                          </p>
                          <p className="mt-0.5 text-sm font-semibold tabular-nums text-neutral-800">
                            {opp.response_deadline
                              ? fmtRelativeDays(
                                  opp.response_deadline,
                                  opp.days_until_deadline
                                )
                              : "—"}
                          </p>
                          <p className="mt-1 text-[11px] text-neutral-400">
                            posted {fmtDate(opp.posted_at)}
                          </p>
                        </div>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
            </KeyboardList>
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
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-accent text-foreground"
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
