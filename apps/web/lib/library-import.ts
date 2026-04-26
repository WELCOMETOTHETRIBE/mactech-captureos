"use server";

import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

const IMPORT_TIMEOUT_MS = 90_000;

type SyncImported = {
  id: string;
  title: string;
  extracted_text_chars: number;
  edit_url: string;
  notes: string[];
};

type AsyncQueued = {
  job_id: string;
  status: string;
  poll_url: string;
  message: string;
};

/**
 * Either the API returns 201 with the new record (text PDF, sync path),
 * or 202 with a job_id (scanned PDF, OCR runs async in the worker).
 */
type ImportResponse =
  | { kind: "sync"; record: SyncImported }
  | { kind: "queued"; job: AsyncQueued };

async function _importViaPdf(
  formData: FormData,
  apiPath: string
): Promise<ImportResponse> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    throw new Error("Pick a PDF before clicking Import.");
  }

  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    throw new Error("Not signed in.");
  }

  const upload = new FormData();
  upload.append("file", file, file.name);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), IMPORT_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${apiPath}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: upload,
      cache: "no-store",
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 202) {
    const queued = (await res.json()) as AsyncQueued;
    return { kind: "queued", job: queued };
  }
  if (!res.ok) {
    let detail: string;
    try {
      const j = (await res.json()) as { detail?: string };
      detail = j.detail ?? `import failed (${res.status})`;
    } catch {
      detail = `import failed (${res.status})`;
    }
    throw new Error(detail);
  }
  const record = (await res.json()) as SyncImported;
  return { kind: "sync", record };
}

export async function importPastPerformanceFromPdf(
  formData: FormData
): Promise<void> {
  const result = await _importViaPdf(
    formData,
    "/library/import/past-performance/from-pdf"
  );
  revalidatePath("/library");
  if (result.kind === "sync") {
    redirect(result.record.edit_url);
  } else {
    redirect(`/library/import/jobs/${result.job.job_id}`);
  }
}

export async function importCapabilityStatementFromPdf(
  formData: FormData
): Promise<void> {
  const result = await _importViaPdf(
    formData,
    "/library/import/capability-statements/from-pdf"
  );
  revalidatePath("/library");
  if (result.kind === "sync") {
    redirect(result.record.edit_url);
  } else {
    redirect(`/library/import/jobs/${result.job.job_id}`);
  }
}
