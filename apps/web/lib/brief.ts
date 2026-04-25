"use server";

import { revalidatePath } from "next/cache";
import { apiFetch, type BriefOut } from "@/lib/api";

const BRIEF_TIMEOUT_MS = 60_000;

/**
 * Server actions for the structured opportunity brief that replaces
 * the raw SAM <pre> on the detail page.
 */

export async function generateOpportunityBrief(
  opportunityId: string
): Promise<void> {
  await apiFetch<BriefOut>(`/opportunities/${opportunityId}/brief`, {
    method: "POST",
    body: JSON.stringify({}),
    timeoutMs: BRIEF_TIMEOUT_MS
  });
  revalidatePath(`/opportunities/${opportunityId}`);
}

export async function deleteOpportunityBrief(formData: FormData): Promise<void> {
  const opportunityId = String(formData.get("opportunity_id") ?? "");
  if (!opportunityId) throw new Error("missing opportunity_id");
  await apiFetch<void>(`/opportunities/${opportunityId}/brief`, {
    method: "DELETE"
  });
  revalidatePath(`/opportunities/${opportunityId}`);
}
