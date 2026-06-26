import Link from "next/link";
import { notFound } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Badge, PageHeader, fmtDate } from "@/components/ui";

export const dynamic = "force-dynamic";

type SBIRFile = { path: string; bytes: number };
type SBIRDetail = {
  id: string;
  topic_number: string;
  topic_title: string | null;
  proposal_title: string | null;
  component: string;
  depth: string;
  status: string;
  output_dir: string;
  verify_flags: string[];
  file_count: number;
  error: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  files: SBIRFile[];
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

export default async function SBIRDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let sub: SBIRDetail;
  try {
    sub = await apiFetch<SBIRDetail>(`/sbir/submissions/${id}`);
  } catch (err) {
    console.error("failed to load /sbir/submissions/{id}", err);
    notFound();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`SBIR · ${sub.component}`}
        title={sub.topic_number}
        subtitle={sub.topic_title ?? "(no topic title on file)"}
        trailing={<Badge tone={STATUS_TONE[sub.status] ?? "neutral"}>{sub.status}</Badge>}
      />

      <section className="grid gap-4 md:grid-cols-3">
        <Stat label="Depth" value={sub.depth} />
        <Stat label="Files" value={String(sub.file_count)} />
        <Stat
          label="Tokens"
          value={
            sub.input_tokens != null && sub.output_tokens != null
              ? `${sub.input_tokens.toLocaleString()} in / ${sub.output_tokens.toLocaleString()} out`
              : "—"
          }
        />
        <Stat label="Started" value={fmtDate(sub.created_at)} />
        <Stat
          label="Finished"
          value={sub.completed_at ? fmtDate(sub.completed_at) : "—"}
        />
        <Stat label="Model" value={sub.model ?? "—"} />
      </section>

      {sub.error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
          <p className="font-medium text-destructive">Run failed</p>
          <p className="mt-1 whitespace-pre-wrap text-foreground">{sub.error}</p>
        </div>
      )}

      {sub.verify_flags.length > 0 && (
        <section className="rounded-md border border-warning/40 bg-warning/10 p-3">
          <p className="text-sm font-medium text-foreground">
            Verify flags — resolve before DSIP certification
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-foreground">
            {sub.verify_flags.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Artifacts
          </h2>
          <p className="text-xs text-muted-foreground">
            On disk at <code className="rounded bg-muted px-1.5 py-0.5">{sub.output_dir}</code>
          </p>
        </div>
        {sub.files.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No files on disk yet. {sub.status === "running" ? "Generation in progress." : ""}
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-md border border-border bg-card">
            {sub.files.map((f) => (
              <li
                key={f.path}
                className="flex items-center justify-between gap-3 px-4 py-2 text-sm"
              >
                <Link
                  href={`/sbir/submissions/${sub.id}/files/${f.path}`}
                  className="truncate text-primary hover:underline"
                >
                  {f.path}
                </Link>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {f.bytes.toLocaleString()} bytes
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-xs text-muted-foreground">
        <Link href="/sbir" className="hover:underline">
          ← back to SBIR Submission Engine
        </Link>
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card p-3">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}
