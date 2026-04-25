import Link from "next/link";
import { apiFetch, type DashboardResponse } from "@/lib/api";
import {
  Badge,
  Card,
  EmptyState,
  Kpi,
  NoticeTypeBadge,
  PageHeader,
  Pillar,
  ScoreBadge,
  SetAsideBadge,
  fmtDate,
  fmtMoney,
  fmtRelativeDays
} from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const data = await apiFetch<DashboardResponse>("/me/dashboard");

  const greeting = data.you
    ? `Good morning, ${data.you.full_name.split(" ")[0]}.`
    : "Dashboard";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="This week"
        title={greeting}
        subtitle={
          data.you ? (
            <span className="inline-flex items-center gap-2">
              <Pillar pillar={data.you.pillar} />
              <span className="text-neutral-500">·</span>
              <span>{data.you.title}</span>
              {data.you.email && (
                <>
                  <span className="text-neutral-500">·</span>
                  <span>{data.you.email}</span>
                </>
              )}
            </span>
          ) : undefined
        }
        trailing={
          <Link
            href="/opportunities"
            className="rounded-md border border-neutral-300 px-3 py-2 text-sm hover:border-neutral-500"
          >
            Browse all →
          </Link>
        }
      />

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi
          label="Opportunities"
          value={data.kpis.opportunities_total.toLocaleString()}
          hint="all time, this tenant"
        />
        <Kpi
          label="Posted last 24h"
          value={data.kpis.opportunities_last_24h.toLocaleString()}
          hint="ingested by SAM worker"
        />
        <Kpi
          label="Scored ≥ 60"
          value={data.kpis.scored_above_60.toLocaleString()}
          hint="digest-eligible"
        />
        <Kpi
          label="Incumbent intel"
          value={data.kpis.enriched_with_incumbent.toLocaleString()}
          hint="USASpending matched"
        />
      </section>

      <section>
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
            Your top {data.your_top.length}
          </h2>
          {data.you && (
            <Link
              href={`/opportunities?assigned_founder=${data.you.slug}&score_min=60`}
              className="text-xs text-blue-700 hover:underline"
            >
              See all your assigned →
            </Link>
          )}
        </div>
        {data.your_top.length === 0 ? (
          <div className="mt-3">
            <EmptyState
              title="No opportunities scored ≥ 60 in your lane today."
              body="Ingestion runs every 2 hours, scoring every 20 minutes. Check back after the next sweep — or browse all opportunities."
              action={
                <Link
                  href="/opportunities"
                  className="rounded-md border border-neutral-300 px-3 py-2 text-sm hover:border-neutral-500"
                >
                  Browse opportunities
                </Link>
              }
            />
          </div>
        ) : (
          <ul className="mt-3 space-y-3">
            {data.your_top.map((opp, i) => (
              <li key={opp.id}>
                <Link
                  href={opp.detail_url}
                  className="block rounded-md border border-neutral-200 bg-white p-5 transition-colors hover:border-neutral-400"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] uppercase tracking-wider text-neutral-500">
                        #{i + 1}
                      </span>
                      <ScoreBadge score={opp.score} />
                      <NoticeTypeBadge type={opp.notice_type} />
                      {opp.set_aside && <SetAsideBadge code={opp.set_aside} />}
                    </div>
                    <p className="text-xs text-neutral-500 tabular-nums">
                      {fmtRelativeDays(opp.response_deadline, null)}
                    </p>
                  </div>
                  <h3 className="mt-2 text-base font-semibold text-neutral-900">
                    {opp.title}
                  </h3>
                  <p className="mt-1 text-xs text-neutral-500">
                    {[
                      opp.agency_short,
                      opp.naics_code && `NAICS ${opp.naics_code}`,
                      `posted ${fmtDate(opp.posted_at)}`
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  {opp.why_it_matters && (
                    <p className="mt-3 text-sm leading-relaxed text-neutral-700">
                      {opp.why_it_matters}
                    </p>
                  )}
                  {opp.incumbent_name && (
                    <p className="mt-3 text-xs text-neutral-600">
                      <span className="font-medium text-neutral-800">Incumbent:</span>{" "}
                      {opp.incumbent_name}
                      {opp.incumbent_amount != null &&
                        ` — ${fmtMoney(opp.incumbent_amount)} prior obligations`}
                    </p>
                  )}
                  <p className="mt-3 text-xs text-blue-700">View detail →</p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
          Pillars
        </h2>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          {data.pillar_cards.map((p) => (
            <Link
              key={p.slug}
              href={`/opportunities?assigned_founder=${p.slug}&score_min=60`}
              className="block rounded-md border border-neutral-200 bg-white p-4 transition-colors hover:border-neutral-400"
            >
              <div className="flex items-center justify-between gap-2">
                <Pillar pillar={p.pillar} />
                <Badge tone="neutral">@{p.slug}</Badge>
              </div>
              <p className="mt-2 text-sm font-medium text-neutral-900">{p.full_name}</p>
              <p className="mt-2 text-2xl font-semibold tabular-nums">{p.high_score_count}</p>
              <p className="text-xs text-neutral-500">scored ≥ 60</p>
            </Link>
          ))}
        </div>
      </section>

      <footer className="pt-2 text-xs text-neutral-500">
        Last refreshed {fmtDate(data.rendered_at)}
      </footer>
    </div>
  );
}
