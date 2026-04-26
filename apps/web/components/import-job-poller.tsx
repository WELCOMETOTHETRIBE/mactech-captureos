"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

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

const POLL_INTERVAL_MS = 3000;

export function ImportJobPoller({
  jobId,
  initial
}: {
  jobId: string;
  initial: JobStatus;
}) {
  const router = useRouter();
  const [job, setJob] = useState<JobStatus>(initial);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    if (initial.status === "done" && initial.edit_url) {
      router.replace(initial.edit_url);
      return;
    }
    if (initial.status === "done" || initial.status === "failed") {
      return;
    }

    const tick = async () => {
      try {
        const res = await fetch(`/library/import/jobs/${jobId}/status`, {
          cache: "no-store"
        });
        if (!res.ok) {
          return;
        }
        const next = (await res.json()) as JobStatus;
        if (cancelled.current) return;
        setJob(next);
        if (next.status === "done" && next.edit_url) {
          router.replace(next.edit_url);
        }
      } catch {
        // Network blip — try again on the next tick.
      }
    };

    const id = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled.current = true;
      clearInterval(id);
    };
  }, [jobId, initial, router]);

  if (job.status === "failed") {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-900">
        <p className="font-medium">Import failed</p>
        <p className="mt-2 whitespace-pre-wrap">
          {job.error_message ?? "Unknown error."}
        </p>
        <p className="mt-3 text-xs text-rose-700">
          Try a higher-resolution scan, or paste the content into the manual
          form.
        </p>
      </div>
    );
  }

  if (job.status === "done") {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-6 text-sm text-emerald-900">
        <p className="font-medium">Import complete — taking you there now…</p>
      </div>
    );
  }

  const label =
    job.status === "queued"
      ? "Queued — waiting for a worker to pick this up."
      : "Running OCR + extraction. Hang tight, this usually takes 30 s – 2 min.";

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-6">
      <div className="flex items-center gap-3">
        <span
          className="inline-block h-3 w-3 animate-pulse rounded-full bg-brand-500"
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-neutral-900">{label}</p>
      </div>
      <p className="mt-3 text-xs text-neutral-500">
        We&rsquo;ll redirect you to the edit page automatically when it&rsquo;s
        done. Safe to leave this tab open or come back later from the library.
      </p>
      {job.filename ? (
        <p className="mt-4 text-xs text-neutral-500">
          File: <span className="text-neutral-700">{job.filename}</span>
        </p>
      ) : null}
    </div>
  );
}
