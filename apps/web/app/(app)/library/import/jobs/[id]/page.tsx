import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { ImportJobPoller } from "@/components/import-job-poller";

export const dynamic = "force-dynamic";

type JobStatus = {
  id: string;
  kind: string;
  status: "queued" | "running" | "done" | "failed";
  filename: string | null;
  result_id: string | null;
  edit_url: string | null;
  text_chars: number | null;
  notes: string[];
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

const KIND_TO_LABEL: Record<string, string> = {
  past_performance: "Past performance",
  capability_statement: "Capability statement"
};

export default async function ImportJobPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let job: JobStatus;
  try {
    job = await apiFetch<JobStatus>(`/library/import/jobs/${id}`);
  } catch {
    notFound();
  }

  const kindLabel = KIND_TO_LABEL[job.kind] ?? "Library import";

  return (
    <div className="space-y-6">
      <Link
        href="/library"
        className="text-xs text-neutral-500 hover:text-neutral-800"
      >
        ← Library
      </Link>

      <PageHeader
        eyebrow={kindLabel}
        title="Importing scanned PDF…"
        subtitle={
          <span>
            Your PDF didn&rsquo;t have a text layer, so we&rsquo;re running
            OCR + Claude extraction on a worker. This page polls the job
            every few seconds and will jump you to the edit page when it
            finishes.
          </span>
        }
      />

      <ImportJobPoller jobId={id} initial={job} />
    </div>
  );
}
