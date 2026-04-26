"use server";

import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

const IMPORT_TIMEOUT_MS = 90_000;

type ImportedRecord = {
  id: string;
  title: string;
  extracted_text_chars: number;
  edit_url: string;
  notes: string[];
};

async function _importViaPdf(
  formData: FormData,
  apiPath: string
): Promise<ImportedRecord> {
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
  return (await res.json()) as ImportedRecord;
}

/**
 * Server action: receives a PDF file from the browser, uploads to the
 * API, redirects to the edit page for the freshly-extracted record.
 */
export async function importPastPerformanceFromPdf(
  formData: FormData
): Promise<void> {
  const result = await _importViaPdf(
    formData,
    "/library/import/past-performance/from-pdf"
  );
  revalidatePath("/library");
  redirect(result.edit_url);
}

export async function importCapabilityStatementFromPdf(
  formData: FormData
): Promise<void> {
  const result = await _importViaPdf(
    formData,
    "/library/import/capability-statements/from-pdf"
  );
  revalidatePath("/library");
  redirect(result.edit_url);
}
