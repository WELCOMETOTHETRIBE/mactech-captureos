import Link from "next/link";

import type { CaptureQueueItem, CaptureQueues as CaptureQueuesData } from "@/lib/api";

function fmtDeadline(iso: string | null): string {
  if (!iso) return "no deadline";
  const d = new Date(iso);
  const days = Math.ceil((d.getTime() - Date.now()) / 86_400_000);
  const date = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  if (days < 0) return `${date} (expired)`;
  return `${date} (${days}d)`;
}

function QueueCard({ item }: { item: CaptureQueueItem }) {
  return (
    <Link
      href={`/opportunities/${item.opportunity_id}`}
      className="block rounded-md border border-border bg-card p-3 hover:border-foreground/30"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium leading-snug">{item.title}</span>
        <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs tabular-nums">
          {item.overall_priority}
        </span>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        {item.naics_code && <span>NAICS {item.naics_code}</span>}
        <span>{item.set_aside || "unrestricted"}</span>
        <span>{fmtDeadline(item.response_deadline)}</span>
      </div>
      {item.prime_target_names.length > 0 && (
        <div className="mt-1 text-xs text-sky-300">
          primes: {item.prime_target_names.slice(0, 2).join(", ")}
        </div>
      )}
      {item.next_action && (
        <div className="mt-1 line-clamp-1 text-xs text-muted-foreground">→ {item.next_action}</div>
      )}
    </Link>
  );
}

function Queue({
  title,
  accent,
  items,
}: {
  title: string;
  accent: string;
  items: CaptureQueueItem[];
}) {
  return (
    <div className="flex-1 min-w-[240px] space-y-2">
      <div className="flex items-center justify-between">
        <h3 className={`text-sm font-semibold ${accent}`}>{title}</h3>
        <span className="text-xs text-muted-foreground tabular-nums">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
          Nothing here right now.
        </p>
      ) : (
        <div className="space-y-2">
          {items.slice(0, 6).map((it) => (
            <QueueCard key={it.opportunity_id} item={it} />
          ))}
        </div>
      )}
    </div>
  );
}

export function CaptureQueues({ data }: { data: CaptureQueuesData }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold">This week</h2>
        <p className="text-xs text-muted-foreground">
          Operational queues from the decision engine — not a keyword score.
        </p>
      </div>
      <div className="flex flex-wrap gap-4">
        <Queue title="Pursue as Prime" accent="text-emerald-400" items={data.pursue_as_prime} />
        <Queue title="Team as Sub" accent="text-sky-400" items={data.team_as_sub} />
        <Queue title="Shape Early" accent="text-amber-400" items={data.shape_early} />
        <Queue title="Needs Review" accent="text-muted-foreground" items={data.needs_review} />
      </div>
    </section>
  );
}
