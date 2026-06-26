import { apiFetch } from "@/lib/api";
import { Badge, EmptyState, PageHeader, fmtDate } from "@/components/ui";
import { SBIRRunner } from "@/components/sbir-runner";
import Link from "next/link";

export const dynamic = "force-dynamic";

type SBIRSubmissionListItem = {
  id: string;
  topic_number: string;
  topic_title: string | null;
  component: string;
  depth: string;
  status: string;
  file_count: number;
  created_at: string;
  completed_at: string | null;
};

type SBIRSubmissionListResponse = {
  total: number;
  items: SBIRSubmissionListItem[];
};

const STATUS_TONE: Record<
  string,
  "neutral" | "blue" | "green" | "amber" | "red"
> = {
  queued: "neutral",
  running: "blue",
  completed: "green",
  failed: "red"
};

export default async function SBIRPage() {
  let history: SBIRSubmissionListResponse = { total: 0, items: [] };
  try {
    history = await apiFetch<SBIRSubmissionListResponse>("/sbir/submissions");
  } catch (err) {
    console.error("Failed to load /sbir/submissions", err);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="SBIR Submission Engine"
        title="SBIR Searcher & Submitter"
        subtitle={
          <>
            Turn a SBIR topic announcement plus your synergy hypothesis into a
            certifiable DoW Phase I submission package — seven volumes, DSIP
            cheat sheet, Corporate Official email, evidence-pack scaffold. Every
            claim traces to a verified firm record, the topic PDF, or an
            explicit user input.
          </>
        }
      />

      <SBIRRunner />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Past submissions
        </h2>
        {history.items.length === 0 ? (
          <EmptyState
            title="No submissions yet."
            body="Run the engine above to generate your first package. Past runs appear here and remain downloadable from disk."
          />
        ) : (
          <ul className="space-y-2">
            {history.items.map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-baseline justify-between gap-3 rounded-md border border-border bg-card p-4"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={STATUS_TONE[s.status] ?? "neutral"}>
                      {s.status}
                    </Badge>
                    <span className="font-medium text-foreground">
                      {s.topic_number}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {s.component} · {s.depth}
                    </span>
                  </div>
                  {s.topic_title && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {s.topic_title}
                    </p>
                  )}
                </div>
                <div className="text-right text-xs text-muted-foreground">
                  <p>
                    {s.file_count} file{s.file_count === 1 ? "" : "s"} ·
                    started {fmtDate(s.created_at)}
                  </p>
                  {s.completed_at && (
                    <p>finished {fmtDate(s.completed_at)}</p>
                  )}
                  <Link
                    href={`/sbir/${s.id}`}
                    className="mt-1 inline-block text-primary hover:underline"
                  >
                    open →
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
