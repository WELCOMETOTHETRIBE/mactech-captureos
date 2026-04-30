"use server";

import { revalidatePath } from "next/cache";
import {
  apiFetch,
  type PursuitCard,
  type PursuitDetailOut,
  type PursuitStage,
} from "@/lib/api";

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

export type BidDecision = "pending" | "bid" | "no_bid";

export async function updatePursuit(input: {
  pursuitId: string;
  opportunityId: string;
  stage?: PursuitStage;
  ownerFounderSlug?: string | null;
  clearOwner?: boolean;
  notes?: string | null;
  winThemes?: string[];
  discriminators?: string[];
  bidDecision?: BidDecision;
  bidRationale?: string | null;
}): Promise<PursuitCard> {
  const body: Record<string, unknown> = {};
  if (input.stage) body.stage = input.stage;
  if (input.clearOwner) {
    body.clear_owner = true;
  } else if (input.ownerFounderSlug !== undefined) {
    body.owner_founder_slug = input.ownerFounderSlug;
  }
  if (input.notes !== undefined) body.notes = input.notes;
  if (input.winThemes !== undefined) body.win_themes = input.winThemes;
  if (input.discriminators !== undefined) body.discriminators = input.discriminators;
  if (input.bidDecision !== undefined) body.bid_decision = input.bidDecision;
  if (input.bidRationale !== undefined) body.bid_rationale = input.bidRationale;

  const card = await apiFetch<PursuitCard>(`/pursuits/${input.pursuitId}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  revalidatePath("/pipeline");
  revalidatePath(`/opportunities/${input.opportunityId}`);
  revalidatePath(`/pursuits/${input.pursuitId}`);
  revalidatePath(`/pursuits/${input.pursuitId}/capture-package`);
  return card;
}

export async function updatePursuitBidDecision(
  pursuitId: string,
  opportunityId: string,
  decision: BidDecision,
  rationale: string | null
): Promise<void> {
  await updatePursuit({
    pursuitId,
    opportunityId,
    bidDecision: decision,
    bidRationale: rationale,
  });
}

export async function deletePursuit(input: {
  pursuitId: string;
  opportunityId: string;
}): Promise<void> {
  await apiFetch<void>(`/pursuits/${input.pursuitId}`, { method: "DELETE" });
  revalidatePath("/pipeline");
  revalidatePath(`/opportunities/${input.opportunityId}`);
}

export async function replacePursuitPastPerformance(
  pursuitId: string,
  pastPerformanceIds: string[]
): Promise<void> {
  await apiFetch<PursuitDetailOut>(
    `/pursuits/${pursuitId}/past-performance`,
    {
      method: "PUT",
      body: JSON.stringify({ past_performance_ids: pastPerformanceIds }),
    }
  );
  revalidatePath(`/pursuits/${pursuitId}`);
  revalidatePath(`/pursuits/${pursuitId}/capture-package`);
}

export async function replacePursuitKeyPersonnel(
  pursuitId: string,
  founderIds: string[]
): Promise<void> {
  await apiFetch<PursuitDetailOut>(`/pursuits/${pursuitId}/key-personnel`, {
    method: "PUT",
    body: JSON.stringify({ founder_ids: founderIds }),
  });
  revalidatePath(`/pursuits/${pursuitId}`);
  revalidatePath(`/pursuits/${pursuitId}/capture-package`);
}

export async function replacePursuitTeamingPartners(
  pursuitId: string,
  teamingPartnerIds: string[]
): Promise<void> {
  await apiFetch<PursuitDetailOut>(
    `/pursuits/${pursuitId}/teaming-partners`,
    {
      method: "PUT",
      body: JSON.stringify({ teaming_partner_ids: teamingPartnerIds }),
    }
  );
  revalidatePath(`/pursuits/${pursuitId}`);
  revalidatePath(`/pursuits/${pursuitId}/capture-package`);
}

export async function updatePursuitWinStrategy(
  pursuitId: string,
  opportunityId: string,
  winThemes: string[],
  discriminators: string[]
): Promise<void> {
  await updatePursuit({
    pursuitId,
    opportunityId,
    winThemes,
    discriminators,
  });
}
