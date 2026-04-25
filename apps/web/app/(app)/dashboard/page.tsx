import { apiFetch, type DashboardResponse } from "@/lib/api";

export const dynamic = "force-dynamic";

function fmtMoney(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n.toFixed(0)}`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  });
}

export default async function DashboardPage() {
  const data = await apiFetch<DashboardResponse>("/me/dashboard");

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wider text-neutral-500">This Week</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          {data.you ? `Good morning, ${data.you.full_name.split(" ")[0]}.` : "Dashboard"}
        </h1>
        {data.you && (
          <p className="mt-1 text-sm text-neutral-600">
            <span className="capitalize">{data.you.pillar}</span> pillar
            {" · "}
            {data.you.email ?? "no email on file"}
          </p>
        )}
      </header>

      {/* KPI cards */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Opportunities" value={data.kpis.opportunities_total.toLocaleString()} />
        <Kpi label="Posted last 24h" value={data.kpis.opportunities_last_24h.toLocaleString()} />
        <Kpi label="Scored ≥ 60" value={data.kpis.scored_above_60.toLocaleString()} />
        <Kpi
          label="With incumbent intel"
          value={data.kpis.enriched_with_incumbent.toLocaleString()}
        />
      </section>

      {/* Your top */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
          Your top {data.your_top.length}
        </h2>
        {data.your_top.length === 0 ? (
          <div className="mt-3 rounded-md border border-neutral-200 bg-white p-5 text-sm text-neutral-600">
            No opportunities scored above 60 in your lane today. The ingestion sweep runs every
            2 hours and the scoring engine catches up on the next 20-min beat.
          </div>
        ) : (
          <ul className="mt-3 space-y-3">
            {data.your_top.map((opp, i) => (
              <li
                key={opp.id}
                className="rounded-md border border-neutral-200 bg-white p-5"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                    #{i + 1} · score {opp.score}
                  </p>
                  <p className="text-xs text-neutral-500">{fmtDate(opp.posted_at)}</p>
                </div>
                <h3 className="mt-1 text-base font-semibold text-neutral-900">{opp.title}</h3>
                <p className="mt-1 text-xs text-neutral-500">
                  {[opp.notice_type, opp.set_aside, opp.naics_code && `NAICS ${opp.naics_code}`, opp.agency_short]
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
                    {opp.incumbent_amount != null && ` — ${fmtMoney(opp.incumbent_amount)} prior obligations`}
                  </p>
                )}
                {opp.sam_link && (
                  <a
                    href={opp.sam_link}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-block text-xs text-blue-700 hover:underline"
                  >
                    View on SAM.gov →
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Pillar cards */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
          Pillars
        </h2>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          {data.pillar_cards.map((p) => (
            <div
              key={p.slug}
              className="rounded-md border border-neutral-200 bg-white p-4"
            >
              <p className="text-[11px] uppercase tracking-wider text-neutral-500 capitalize">
                {p.pillar}
              </p>
              <p className="mt-1 text-sm font-medium text-neutral-900">{p.full_name}</p>
              <p className="mt-2 text-2xl font-semibold tabular-nums">{p.high_score_count}</p>
              <p className="text-xs text-neutral-500">scored ≥ 60</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="pt-4 text-xs text-neutral-500">
        Last refreshed {fmtDate(data.rendered_at)}
      </footer>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-neutral-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wider text-neutral-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}
