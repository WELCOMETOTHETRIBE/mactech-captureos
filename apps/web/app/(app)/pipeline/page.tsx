import Link from "next/link";
import { Card, EmptyState, PageHeader } from "@/components/ui";

export const dynamic = "force-dynamic";

const STAGES = [
  { key: "lead", label: "Lead", desc: "Newly scored, not yet triaged." },
  { key: "qualify", label: "Qualify", desc: "Reviewing fit, set-aside, ceiling." },
  { key: "pursue", label: "Pursue", desc: "Drafting capability response." },
  { key: "propose", label: "Propose", desc: "Solicitation in hand, writing." },
  { key: "submit", label: "Submit", desc: "Submitted — awaiting decision." },
  { key: "won_lost", label: "Won / Lost", desc: "Closed, post-mortem due." }
];

export default function PipelinePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Capture pipeline"
        title="Pursuit kanban"
        subtitle="Lead → Qualify → Pursue → Propose → Submit → Won/Lost. The full kanban with drag-and-drop, owner assignment, and status notes ships in Phase 2 Week 7."
      />

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {STAGES.map((s) => (
          <Card key={s.key} title={s.label}>
            <p className="text-sm text-neutral-600">{s.desc}</p>
            <p className="mt-3 text-[11px] uppercase tracking-wider text-neutral-400">
              ships Phase 2 Week 7
            </p>
          </Card>
        ))}
      </div>

      <EmptyState
        title="The pipeline UI is not live yet."
        body="In the meantime, opportunities are scored, assigned, and surfaced in the morning digest. Open the dashboard or browse all opportunities to triage."
        action={
          <div className="flex justify-center gap-2">
            <Link
              href="/dashboard"
              className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-800"
            >
              Open dashboard
            </Link>
            <Link
              href="/opportunities"
              className="rounded-md border border-neutral-300 px-3 py-2 text-sm hover:border-neutral-500"
            >
              Browse opportunities
            </Link>
          </div>
        }
      />
    </div>
  );
}
