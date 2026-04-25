"use server";

import { revalidatePath } from "next/cache";
import { apiFetch, type PursuitCard, type PursuitStage } from "@/lib/api";

/**
 * Server actions for the capture pipeline kanban. All run on the server
 * with the caller's Clerk session, then revalidate the pages that show
 * the pursuit so the UI updates without a manual refresh.
 */

export async function createPursuit(input: {
  opportunityId: string;
  stage?: PursuitStage;
  ownerFounderSlug?: string | null;
  notes?: string | null;
}): Promise<PursuitCard> {
  const card = await apiFetch<PursuitCard>("/pursuits", {
    method: "POST",
    body: JSON.stringify({
      opportunity_id: input.opportunityId,
      stage: input.stage ?? "lead",
      owner_founder_slug: input.ownerFounderSlug ?? null,
      notes: input.notes ?? null
    })
  });
  revalidatePath("/pipeline");
  revalidatePath(`/opportunities/${input.opportunityId}`);
  return card;
}

export async function updatePursuit(input: {
  pursuitId: string;
  opportunityId: string;
  stage?: PursuitStage;
  ownerFounderSlug?: string | null;
  clearOwner?: boolean;
  notes?: string | null;
}): Promise<PursuitCard> {
  const body: Record<string, unknown> = {};
  if (input.stage) body.stage = input.stage;
  if (input.clearOwner) {
    body.clear_owner = true;
  } else if (input.ownerFounderSlug !== undefined) {
    body.owner_founder_slug = input.ownerFounderSlug;
  }
  if (input.notes !== undefined) body.notes = input.notes;

  const card = await apiFetch<PursuitCard>(`/pursuits/${input.pursuitId}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  revalidatePath("/pipeline");
  revalidatePath(`/opportunities/${input.opportunityId}`);
  return card;
}

export async function deletePursuit(input: {
  pursuitId: string;
  opportunityId: string;
}): Promise<void> {
  await apiFetch<void>(`/pursuits/${input.pursuitId}`, { method: "DELETE" });
  revalidatePath("/pipeline");
  revalidatePath(`/opportunities/${input.opportunityId}`);
}
