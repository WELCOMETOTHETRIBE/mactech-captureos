import Link from "next/link";
import {
  apiFetch,
  PURSUIT_STAGES_ORDER,
  type KanbanResponse,
  type PursuitCard as PursuitCardT,
  type PursuitStage,
  type SettingsResponse
} from "@/lib/api";
import { createPursuit, deletePursuit, updatePursuit } from "@/lib/pursuits";
import {
  NaicsBadge,
  NoticeTypeBadge,
  PageHeader,
  ScoreBadge,
  SetAsideBadge,
  fmtRelativeDays
} from "@/components/ui";

export const dynamic = "force-dynamic";

const ACTIVE_STAGES: PursuitStage[] = ["lead", "qualify", "pursue", "propose", "submit"];
const TERMINAL_STAGES: PursuitStage[] = ["won", "lost"];

export default async function PipelinePage({
  searchParams
}: {
  searchParams: Promise<{ owner?: string }>;
}) {
  const sp = await searchParams;
  const ownerFilter = sp.owner ?? null;

  const path = ownerFilter
    ? `/pursuits?owner=${encodeURIComponent(ownerFilter)}`
    : "/pursuits";

  const [data, settings] = await Promise.all([
    apiFetch<KanbanResponse>(path),
    apiFetch<SettingsResponse>("/me/settings")
  ]);

  const founders = settings.founders;
  const activeColumns = data.columns.filter((c) =>
    ACTIVE_STAGES.includes(c.stage)
  );
  const terminalColumns = data.columns.filter((c) =>
    TERMINAL_STAGES.includes(c.stage)
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Capture pipeline"
        title="Pursuit kanban"
        subtitle={
          data.total === 0
            ? "No pursuits yet. Open an opportunity and click \u201CAdd to pipeline.\u201D"
            : `${data.total} pursuit${data.total === 1 ? "" : "s"} across ${activeColumns.length} active stages.`
        }
        trailing={
          <div className="flex items-center gap-2">
            {ownerFilter && (
              <Link
                href="/pipeline"
                className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:border-neutral-500"
              >
                Clear owner
              </Link>
            )}
            <Link
              href="/opportunities?score_min=60"
              className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
            >
              Add from opportunities →
            </Link>
          </div>
        }
      />

      {/* Owner filter bar */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-neutral-500">Filter by owner:</span>
        <Link
          href="/pipeline"
          className={pillCls(!ownerFilter)}
        >
          All ({data.total})
        </Link>
        {founders.map((f) => {
          const count = data.by_owner[f.slug] ?? 0;
          return (
            <Link
              key={f.slug}
              href={`/pipeline?owner=${f.slug}`}
              className={pillCls(ownerFilter === f.slug)}
            >
              {f.full_name.split(" ")[0]} ({count})
            </Link>
          );
        })}
        {(data.by_owner._unassigned ?? 0) > 0 && (
          <span className="rounded-md border border-dashed border-neutral-300 px-2 py-1 text-neutral-500">
            unassigned ({data.by_owner._unassigned})
          </span>
        )}
      </div>

      {data.total === 0 ? (
        <FirstTimePipeline />
      ) : (
        <>
          {/* Active stages — horizontal scroll on small screens, 5-col grid on large */}
          <div className="overflow-x-auto pb-2">
            <div className="grid min-w-[1100px] grid-cols-5 gap-3">
              {activeColumns.map((col) => (
                <Column
                  key={col.stage}
                  column={col}
                  founders={founders.map((f) => ({
                    slug: f.slug,
                    full_name: f.full_name
                  }))}
                />
              ))}
            </div>
          </div>

          {/* Terminal stages — collapsed in a smaller row */}
          {terminalColumns.some((c) => c.count > 0) && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {terminalColumns.map((col) => (
                <TerminalColumn
                  key={col.stage}
                  column={col}
                  founders={founders.map((f) => ({
                    slug: f.slug,
                    full_name: f.full_name
                  }))}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function pillCls(active: boolean) {
  return active
    ? "rounded-md bg-neutral-900 px-2 py-1 text-white"
    : "rounded-md border border-neutral-300 px-2 py-1 hover:border-neutral-500";
}

type FounderRef = { slug: string; full_name: string };

function Column({
  column,
  founders
}: {
  column: { stage: PursuitStage; label: string; count: number; cards: PursuitCardT[] };
  founders: FounderRef[];
}) {
  return (
    <section className="flex min-h-[200px] flex-col rounded-md border border-neutral-200 bg-neutral-50 p-3">
      <header className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
          {column.label}
        </h2>
        <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium tabular-nums text-neutral-600 ring-1 ring-neutral-200">
          {column.count}
        </span>
      </header>
      {column.cards.length === 0 ? (
        <p className="text-xs italic text-neutral-400">empty</p>
      ) : (
        <ul className="space-y-2">
          {column.cards.map((c) => (
            <li key={c.id}>
              <Card card={c} founders={founders} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function TerminalColumn({
  column,
  founders
}: {
  column: { stage: PursuitStage; label: string; count: number; cards: PursuitCardT[] };
  founders: FounderRef[];
}) {
  return (
    <section className="rounded-md border border-neutral-200 bg-white p-4">
      <header className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-700">
          {column.stage === "won" ? "✓ Won" : "✗ Lost"}
        </h2>
        <span className="text-[11px] text-neutral-500">{column.count}</span>
      </header>
      {column.cards.length === 0 ? (
        <p className="text-xs italic text-neutral-400">none</p>
      ) : (
        <ul className="space-y-2">
          {column.cards.map((c) => (
            <li key={c.id}>
              <Card card={c} founders={founders} compact />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Card({
  card,
  founders,
  compact = false
}: {
  card: PursuitCardT;
  founders: FounderRef[];
  compact?: boolean;
}) {
  const opp = card.opportunity;
  const stageIdx = PURSUIT_STAGES_ORDER.indexOf(card.stage);
  const canAdvance = stageIdx >= 0 && stageIdx < 4; // up to "submit"
  const canRegress = stageIdx > 0 && stageIdx <= 4;

  // Aging signal: terminal stages (won/lost) never go stale; active stages
  // turn amber at 7 days and red at 14. The visual cue is a colored ring
  // on the card itself so it pops without a badge taking up space.
  const isTerminal = card.stage === "won" || card.stage === "lost";
  const stale = !isTerminal && card.days_in_stage >= 14;
  const warming = !isTerminal && card.days_in_stage >= 7 && card.days_in_stage < 14;
  const cardCls = stale
    ? "rounded-md border-2 border-red-300 bg-white p-3 shadow-sm"
    : warming
    ? "rounded-md border-2 border-amber-300 bg-white p-3 shadow-sm"
    : "rounded-md border border-neutral-200 bg-white p-3 shadow-sm";
  const ageCls = stale
    ? "tabular-nums font-semibold text-red-700"
    : warming
    ? "tabular-nums font-semibold text-amber-700"
    : "tabular-nums text-neutral-500";
  const ageTitle = stale
    ? `Stale: in ${card.stage} for ${card.days_in_stage} days. Move it forward, kill it, or accept it's parked.`
    : warming
    ? `Aging: ${card.days_in_stage} days in ${card.stage}. Time to advance or document why it's parked.`
    : `${card.days_in_stage} days in ${card.stage}.`;

  return (
    <article className={cardCls}>
      <Link
        href={`/opportunities/${opp.id}`}
        className="block hover:underline"
      >
        <div className="flex items-center gap-1.5">
          <ScoreBadge score={opp.score} />
          {opp.notice_type && <NoticeTypeBadge type={opp.notice_type} />}
        </div>
        <h3 className="mt-2 line-clamp-2 text-xs font-semibold leading-snug text-neutral-900">
          {opp.title}
        </h3>
      </Link>

      {!compact && (
        <div className="mt-2 flex flex-wrap gap-1">
          {opp.set_aside && <SetAsideBadge code={opp.set_aside} />}
          <NaicsBadge code={opp.naics_code} />
        </div>
      )}

      {!compact && opp.response_deadline && (
        <p className="mt-2 text-[11px] text-neutral-500">
          {fmtRelativeDays(opp.response_deadline, opp.days_until_deadline)}
        </p>
      )}

      <div className="mt-2 flex items-center justify-between text-[11px]">
        <span className="text-neutral-500">
          {card.owner_founder_slug ? (
            <span className="text-neutral-700">@{card.owner_founder_slug}</span>
          ) : (
            <span className="italic text-neutral-400">unassigned</span>
          )}
        </span>
        <span className={ageCls} title={ageTitle}>
          {card.days_in_stage}d in stage
        </span>
      </div>

      {!compact && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-neutral-100 pt-2">
          {canRegress && (
            <StageBtn
              card={card}
              stage={PURSUIT_STAGES_ORDER[stageIdx - 1]}
              label="←"
              tone="neutral"
            />
          )}
          {canAdvance && (
            <StageBtn
              card={card}
              stage={PURSUIT_STAGES_ORDER[stageIdx + 1]}
              label="→"
              tone="primary"
            />
          )}
          {stageIdx >= 1 && (
            <>
              <StageBtn card={card} stage="won" label="Won" tone="green" />
              <StageBtn card={card} stage="lost" label="Lost" tone="red" />
            </>
          )}
          <OwnerSelect card={card} founders={founders} />
          <RemoveBtn card={card} />
        </div>
      )}

      {compact && (
        <form
          action={async () => {
            "use server";
            await deletePursuit({
              pursuitId: card.id,
              opportunityId: opp.id
            });
          }}
          className="mt-2"
        >
          <button
            type="submit"
            className="text-[10px] text-neutral-400 hover:text-red-700"
          >
            remove
          </button>
        </form>
      )}
    </article>
  );
}

function StageBtn({
  card,
  stage,
  label,
  tone
}: {
  card: PursuitCardT;
  stage: PursuitStage;
  label: string;
  tone: "neutral" | "primary" | "green" | "red";
}) {
  const cls =
    tone === "primary"
      ? "rounded-md bg-neutral-900 px-2 py-0.5 text-white hover:bg-neutral-800"
      : tone === "green"
      ? "rounded-md bg-emerald-600 px-2 py-0.5 text-white hover:bg-emerald-700"
      : tone === "red"
      ? "rounded-md bg-red-600 px-2 py-0.5 text-white hover:bg-red-700"
      : "rounded-md border border-neutral-300 px-2 py-0.5 text-neutral-700 hover:border-neutral-500";

  return (
    <form
      action={async () => {
        "use server";
        await updatePursuit({
          pursuitId: card.id,
          opportunityId: card.opportunity.id,
          stage
        });
      }}
    >
      <button type="submit" className={`text-[10px] font-medium ${cls}`}>
        {label}
      </button>
    </form>
  );
}

function OwnerSelect({
  card,
  founders
}: {
  card: PursuitCardT;
  founders: FounderRef[];
}) {
  return (
    <form
      action={async (formData: FormData) => {
        "use server";
        const slug = String(formData.get("owner") ?? "");
        if (slug === "_clear") {
          await updatePursuit({
            pursuitId: card.id,
            opportunityId: card.opportunity.id,
            clearOwner: true
          });
        } else if (slug) {
          await updatePursuit({
            pursuitId: card.id,
            opportunityId: card.opportunity.id,
            ownerFounderSlug: slug
          });
        }
      }}
      className="flex items-center gap-1"
    >
      <select
        name="owner"
        defaultValue={card.owner_founder_slug ?? ""}
        className="rounded-sm border border-neutral-300 px-1 py-0.5 text-[10px]"
      >
        <option value="" disabled>
          owner
        </option>
        <option value="_clear">— unassigned</option>
        {founders.map((f) => (
          <option key={f.slug} value={f.slug}>
            {f.full_name.split(" ")[0]}
          </option>
        ))}
      </select>
      <button
        type="submit"
        className="rounded-sm border border-neutral-300 px-1 py-0.5 text-[10px] hover:border-neutral-500"
      >
        set
      </button>
    </form>
  );
}

function FirstTimePipeline() {
  return (
    <div className="rounded-md border border-neutral-200 bg-white p-8">
      <p className="text-[11px] uppercase tracking-wider text-neutral-500">
        First time here?
      </p>
      <h2 className="mt-1 text-lg font-semibold text-neutral-900">
        The pipeline is empty.
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-neutral-600">
        The kanban tracks active pursuits. Pursuits land here when you open an
        opportunity and click <em>Add to pipeline</em>. Each pursuit moves
        through six stages — you advance them with one click as the pursuit
        matures.
      </p>

      <ol className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
        <li className="rounded-md border border-neutral-100 bg-neutral-50 p-4">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-neutral-900 text-[10px] font-semibold text-white tabular-nums">
            1
          </span>
          <h3 className="mt-2 text-sm font-semibold text-neutral-900">
            Open an opportunity
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-neutral-600">
            From the dashboard top-5 or the full opportunities feed. Anything
            scoring 60+ is digest-eligible and worth a closer look.
          </p>
        </li>
        <li className="rounded-md border border-neutral-100 bg-neutral-50 p-4">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-neutral-900 text-[10px] font-semibold text-white tabular-nums">
            2
          </span>
          <h3 className="mt-2 text-sm font-semibold text-neutral-900">
            Click &ldquo;Add to pipeline&rdquo;
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-neutral-600">
            On the opportunity detail page, just below the header. The pursuit
            self-assigns to you and lands in the Lead column.
          </p>
        </li>
        <li className="rounded-md border border-neutral-100 bg-neutral-50 p-4">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-neutral-900 text-[10px] font-semibold text-white tabular-nums">
            3
          </span>
          <h3 className="mt-2 text-sm font-semibold text-neutral-900">
            Advance through stages
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-neutral-600">
            Lead &rarr; Qualify &rarr; Pursue &rarr; Propose &rarr; Submit
            &rarr; Won/Lost. Reassign owners or remove from the pipeline at any
            time.
          </p>
        </li>
      </ol>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Link
          href="/opportunities?score_min=60"
          className="rounded-md border border-neutral-900 bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
        >
          Browse scored opportunities &rarr;
        </Link>
        <Link
          href="/dashboard"
          className="rounded-md border border-neutral-300 px-4 py-2 text-sm hover:border-neutral-500"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}

function RemoveBtn({ card }: { card: PursuitCardT }) {
  return (
    <form
      action={async () => {
        "use server";
        await deletePursuit({
          pursuitId: card.id,
          opportunityId: card.opportunity.id
        });
      }}
      className="ml-auto"
    >
      <button
        type="submit"
        className="text-[10px] text-neutral-400 hover:text-red-700"
        title="Remove from pipeline"
      >
        ✕
      </button>
    </form>
  );
}
