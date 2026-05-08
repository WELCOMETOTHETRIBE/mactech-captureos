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
import { TermPopover } from "@/components/term-popover";
import {
  Button,
  LinkButton,
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
            ? "No pursuits yet. Open an opportunity and click “Add to pipeline.”"
            : `${data.total} pursuit${data.total === 1 ? "" : "s"} across ${activeColumns.length} active stages.`
        }
        trailing={
          <div className="flex items-center gap-2">
            {ownerFilter && (
              <LinkButton href="/pipeline" variant="secondary" size="sm">
                Clear owner
              </LinkButton>
            )}
            <LinkButton
              href="/opportunities?score_min=60"
              variant="primary"
              size="sm"
            >
              Add from opportunities →
            </LinkButton>
          </div>
        }
      />

      {/* Owner filter bar */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground">Filter by owner:</span>
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
          <span className="rounded-md border border-dashed border-border px-2 py-1 text-muted-foreground">
            unassigned ({data.by_owner._unassigned})
          </span>
        )}
      </div>

      {/* Stage legend — gives layman readers an inline glossary of the
          7 lifecycle stages without forcing them to open every column. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        <span className="uppercase tracking-wider">Stages:</span>
        <TermPopover kind="pursuit_stage" value="lead">Lead</TermPopover>
        <span aria-hidden>→</span>
        <TermPopover kind="pursuit_stage" value="qualify">Qualify</TermPopover>
        <span aria-hidden>→</span>
        <TermPopover kind="pursuit_stage" value="pursue">Pursue</TermPopover>
        <span aria-hidden>→</span>
        <TermPopover kind="pursuit_stage" value="propose">Propose</TermPopover>
        <span aria-hidden>→</span>
        <TermPopover kind="pursuit_stage" value="submit">Submit</TermPopover>
        <span aria-hidden>→</span>
        <TermPopover kind="pursuit_stage" value="won">Won</TermPopover>
        <span aria-hidden>·</span>
        <TermPopover kind="pursuit_stage" value="lost">Lost</TermPopover>
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
    ? "rounded-md bg-primary px-2 py-1 text-primary-foreground"
    : "rounded-md border border-border px-2 py-1 hover:border-foreground/40";
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
    <section className="flex min-h-[200px] flex-col rounded-md border border-border bg-secondary p-3">
      <header className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
          <TermPopover kind="pursuit_stage" value={column.stage}>
            {column.label}
          </TermPopover>
        </h2>
        <span className="rounded-full bg-card px-2 py-0.5 text-[11px] font-medium tabular-nums text-muted-foreground ring-1 ring-border">
          {column.count}
        </span>
      </header>
      {column.cards.length === 0 ? (
        <p className="text-xs italic text-muted-foreground">empty</p>
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
    <section className="rounded-md border border-border bg-card p-4">
      <header className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
          <TermPopover kind="pursuit_stage" value={column.stage}>
            {column.stage === "won" ? "Won" : "Lost"}
          </TermPopover>
        </h2>
        <span className="text-[11px] text-muted-foreground">{column.count}</span>
      </header>
      {column.cards.length === 0 ? (
        <p className="text-xs italic text-muted-foreground">none</p>
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
    ? "rounded-md border-2 border-destructive/40 bg-card p-3 shadow-sm"
    : warming
    ? "rounded-md border-2 border-warning/40 bg-card p-3 shadow-sm"
    : "rounded-md border border-border bg-card p-3 shadow-sm";
  const ageCls = stale
    ? "tabular-nums font-semibold text-destructive"
    : warming
    ? "tabular-nums font-semibold text-warning"
    : "tabular-nums text-muted-foreground";
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
        <h3 className="mt-2 line-clamp-2 text-xs font-semibold leading-snug text-foreground">
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
        <p className="mt-2 text-[11px] text-muted-foreground">
          {fmtRelativeDays(opp.response_deadline, opp.days_until_deadline)}
        </p>
      )}

      <div className="mt-2 flex items-center justify-between text-[11px]">
        <span className="text-muted-foreground">
          {card.owner_founder_slug ? (
            <span className="text-foreground">@{card.owner_founder_slug}</span>
          ) : (
            <span className="italic text-muted-foreground">unassigned</span>
          )}
        </span>
        <span className={ageCls} title={ageTitle}>
          {card.days_in_stage}d in stage
        </span>
      </div>

      {!compact && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-border pt-2">
          <Link
            href={`/pursuits/${card.id}`}
            className="rounded-md border border-border px-2 py-0.5 text-[11px] text-foreground hover:bg-accent hover:text-accent-foreground"
            title="Open pursuit detail (win themes, asset selection)"
          >
            Open
          </Link>
          <Link
            href={`/pursuits/${card.id}/capture-package`}
            className="rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary hover:bg-primary/15"
            title="Capture Package handoff to ProposalOS"
          >
            Pkg →
          </Link>
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
              <StageBtn card={card} stage="won" label="Won" tone="success" />
              <StageBtn card={card} stage="lost" label="Lost" tone="destructive" />
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
            className="text-[10px] text-muted-foreground hover:text-destructive"
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
  tone: "neutral" | "primary" | "success" | "destructive";
}) {
  // Tone names are semantic and resolve to the design-token Button
  // variants. Won/lost markers are deliberately solid (success/destructive
  // backgrounds) — they're the only places in the kanban where we want
  // the action to read as "this is a terminal commitment."
  const variant: "primary" | "secondary" | "success" | "destructive" =
    tone === "primary"
      ? "primary"
      : tone === "success"
      ? "success"
      : tone === "destructive"
      ? "destructive"
      : "secondary";

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
      <Button type="submit" variant={variant} size="xs">
        {label}
      </Button>
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
        className="rounded-sm border border-border bg-card px-1 py-0.5 text-[10px]"
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
        className="rounded-sm border border-border px-1 py-0.5 text-[10px] hover:border-foreground/40"
      >
        set
      </button>
    </form>
  );
}

function FirstTimePipeline() {
  return (
    <div className="rounded-md border border-border bg-card p-8">
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
        First time here?
      </p>
      <h2 className="mt-1 text-lg font-semibold text-foreground">
        The pipeline is empty.
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        The kanban tracks active pursuits. Pursuits land here when you open an
        opportunity and click <em>Add to pipeline</em>. Each pursuit moves
        through six stages — you advance them with one click as the pursuit
        matures.
      </p>

      <ol className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
        <li className="rounded-md border border-border bg-secondary p-4">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground tabular-nums">
            1
          </span>
          <h3 className="mt-2 text-sm font-semibold text-foreground">
            Open an opportunity
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            From the dashboard top-5 or the full opportunities feed. Anything
            scoring 60+ is digest-eligible and worth a closer look.
          </p>
        </li>
        <li className="rounded-md border border-border bg-secondary p-4">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground tabular-nums">
            2
          </span>
          <h3 className="mt-2 text-sm font-semibold text-foreground">
            Click &ldquo;Add to pipeline&rdquo;
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            On the opportunity detail page, just below the header. The pursuit
            self-assigns to you and lands in the Lead column.
          </p>
        </li>
        <li className="rounded-md border border-border bg-secondary p-4">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground tabular-nums">
            3
          </span>
          <h3 className="mt-2 text-sm font-semibold text-foreground">
            Advance through stages
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Lead &rarr; Qualify &rarr; Pursue &rarr; Propose &rarr; Submit
            &rarr; Won/Lost. Reassign owners or remove from the pipeline at any
            time.
          </p>
        </li>
      </ol>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <LinkButton href="/opportunities?score_min=60" variant="primary">
          Browse scored opportunities &rarr;
        </LinkButton>
        <LinkButton href="/dashboard" variant="secondary">
          Back to dashboard
        </LinkButton>
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
        className="text-[10px] text-muted-foreground hover:text-destructive"
        title="Remove from pipeline"
      >
        ✕
      </button>
    </form>
  );
}
