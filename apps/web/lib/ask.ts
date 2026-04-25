"use server";

import { revalidatePath } from "next/cache";
import { apiFetch, type QuestionOut } from "@/lib/api";

const ASK_TIMEOUT_MS = 60_000;

/**
 * Server actions for the per-opportunity Q&A panel. Synchronous (5–15s
 * for Sonnet); a streaming variant is on the next-sprint backlog.
 */

export async function askOpportunityQuestion(
  opportunityId: string,
  formData: FormData
): Promise<void> {
  const starter = String(formData.get("starter_kind") ?? "").trim() || null;
  const free = String(formData.get("question") ?? "").trim();

  // If neither is provided, throw — there's nothing to ask.
  if (!starter && !free) {
    throw new Error("Type a question or pick a starter.");
  }

  const body = {
    starter_kind: starter,
    // The API resolves the canonical text from starter_kind when set; we
    // still pass the freeform question so it persists if the user typed.
    question: free || starter || "starter"
  };

  await apiFetch<QuestionOut>(
    `/opportunities/${opportunityId}/ask`,
    {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: ASK_TIMEOUT_MS
    }
  );
  revalidatePath(`/opportunities/${opportunityId}`);
}

export async function deleteOpportunityQuestion(
  formData: FormData
): Promise<void> {
  const id = String(formData.get("id") ?? "");
  const oppId = String(formData.get("opportunity_id") ?? "");
  if (!id) throw new Error("missing question id");
  await apiFetch<void>(`/opportunity-questions/${id}`, { method: "DELETE" });
  if (oppId) revalidatePath(`/opportunities/${oppId}`);
}
