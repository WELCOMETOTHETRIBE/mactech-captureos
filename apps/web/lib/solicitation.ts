"use server";

import { revalidatePath } from "next/cache";
import {
  apiFetch,
  type SolicitationExtractionOut,
} from "@/lib/api";

// LLM extraction is a long Sonnet call (often 30–60s for a heavy
// solicitation). Match the brief drafter's generous timeout.
const EXTRACTION_TIMEOUT_MS = 90_000;

/**
 * Trigger Claude to extract the compliance + requirements matrices
 * from the opportunity description. Synchronous — returns when both
 * matrices are persisted. Caller should expect a multi-second wait.
 */
export async function generateSolicitationExtraction(
  opportunityId: string
): Promise<void> {
  await apiFetch<SolicitationExtractionOut>(
    `/opportunities/${opportunityId}/solicitation-extraction`,
    {
      method: "POST",
      body: JSON.stringify({}),
      timeoutMs: EXTRACTION_TIMEOUT_MS,
    }
  );
  revalidatePath(`/opportunities/${opportunityId}`);
}

export async function deleteSolicitationExtraction(
  formData: FormData
): Promise<void> {
  const opportunityId = String(formData.get("opportunity_id") ?? "");
  if (!opportunityId) throw new Error("missing opportunity_id");
  await apiFetch<void>(
    `/opportunities/${opportunityId}/solicitation-extraction`,
    {
      method: "DELETE",
    }
  );
  revalidatePath(`/opportunities/${opportunityId}`);
}
