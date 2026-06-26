import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { Badge, EmptyState, PageHeader, fmtDate } from "@/components/ui";
import { SBIRRunner, type SBIRRunnerInitial } from "@/components/sbir-runner";

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

type SBIRTopicDetail = {
  id: string;
  topic_number: string;
  title: string | null;
  component: string | null;
  description: string | null;
  url: string | null;
  close_date: string | null;
  dsip_enriched_at: string | null;
  dsip_pdf_url: string | null;
  dsip_pdf_text: string | null;
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

const VALID_COMPONENTS = [
  "Army",
  "Navy",
  "Air Force",
  "DLA",
  "DARPA",
  "SOCOM",
  "Other"
] as const;

type ValidComponent = (typeof VALID_COMPONENTS)[number];

function coerceComponent(raw: string | null): ValidComponent | undefined {
  if (!raw) return undefined;
  return (VALID_COMPONENTS as readonly string[]).includes(raw)
    ? (raw as ValidComponent)
    : undefined;
}

export default async function SBIRSubmitPage({
  searchParams
}: {
  searchParams: Promise<{ topic_id?: string }>;
}) {
  const { topic_id } = await searchParams;

  let initial: SBIRRunnerInitial | undefined;
  let prefillNote: string | null = null;
  if (topic_id) {
    try {
      const t = await apiFetch<SBIRTopicDetail>(`/sbir/topics/${topic_id}`);
      // Prefer the verbatim PDF text from DSIP when we have it; fall back
      // to the extracted description; final fallback is the source URL.
      const payload =
        t.dsip_pdf_text && t.dsip_pdf_text.length > 100
          ? t.dsip_pdf_text
          : (t.description ?? t.url ?? "");
      initial = {
        topicNumber: t.topic_number,
        topicTitle: t.title,
        component: coerceComponent(t.component),
        topicPayload: payload,
        sourceKind: t.dsip_pdf_text ? "pdf" : payload ? "text" : "text",
        topicCloseDate: t.close_date
      };
      const sourceLabel = t.dsip_pdf_text
        ? "DSIP PDF source"
        : t.dsip_enriched_at
          ? "DSIP rendered text"
          : "sbirdashboard listing";
      prefillNote = `Pre-filled from topic ${t.topic_number}${t.title ? ` — ${t.title}` : ""} (${sourceLabel}).`;
    } catch (err) {
      console.error("topic prefill failed", err);
      prefillNote = `Could not load topic ${topic_id}; starting blank.`;
    }
  }

  let history: SBIRSubmissionListResponse = { total: 0, items: [] };
  try {
    history = await apiFetch<SBIRSubmissionListResponse>("/sbir/submissions");
  } catch (err) {
    console.error("Failed to load /sbir/submissions", err);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="SBIR · Submit"
        title="Generate a submission package"
        subtitle={
          <>
            Turn a SBIR topic announcement plus your synergy hypothesis into a
            certifiable DoW Phase I submission package. Every claim traces to a
            verified firm record, the topic, or an explicit user input.
          </>
        }
        trailing={
          <Link
            href="/sbir"
            className="text-xs text-muted-foreground hover:text-foreground hover:underline"
          >
            ← Topics
          </Link>
        }
      />

      {prefillNote && (
        <p className="rounded-md border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
          {prefillNote}
        </p>
      )}

      <SBIRRunner initial={initial} />

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
                    href={`/sbir/submissions/${s.id}`}
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
