"use server";

import { revalidatePath } from "next/cache";
import { apiFetch } from "@/lib/api";

export async function deleteOpportunityQuestion(
  formData: FormData
): Promise<void> {
  const id = String(formData.get("id") ?? "");
  const oppId = String(formData.get("opportunity_id") ?? "");
  if (!id) throw new Error("missing question id");
  await apiFetch<void>(`/opportunity-questions/${id}`, { method: "DELETE" });
  if (oppId) revalidatePath(`/opportunities/${oppId}`);
}
