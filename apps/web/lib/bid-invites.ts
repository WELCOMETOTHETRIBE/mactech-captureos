"use server";

import { revalidatePath } from "next/cache";
import {
  apiFetch,
  type BidInvitePursueResult,
  type BidInviteStatus
} from "@/lib/api";

/**
 * Server actions for bid-invite triage. Same contract as lib/pursuits:
 * run with the caller's Clerk session, then revalidate every surface
 * that shows invites so the UI refreshes without a manual reload.
 */

function revalidateInviteSurfaces() {
  revalidatePath("/bid-invites");
  revalidatePath("/dashboard");
}

export async function setBidInviteStatus(
  inviteId: string,
  status: BidInviteStatus
): Promise<void> {
  await apiFetch(`/bid-invites/${inviteId}`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
  revalidateInviteSurfaces();
}

/** Triage a whole project group in one click (e.g. "Mark reviewed"
 * on a card holding an invite + two reminders). Sequential on purpose:
 * groups are small (2–6 emails) and it keeps the API's session
 * handling simple. */
/** Promote an invite's project into the capture pipeline. The API
 * creates (or reuses) a buildingconnected-sourced opportunity + pursuit,
 * links the whole email group, and flips new emails to reviewed —
 * owner defaults to the keyword-routed founder suggestion. */
export async function pursueBidInvite(inviteId: string): Promise<void> {
  await apiFetch<BidInvitePursueResult>(`/bid-invites/${inviteId}/pursue`, {
    method: "POST",
    body: JSON.stringify({})
  });
  revalidateInviteSurfaces();
  revalidatePath("/pipeline");
}

export async function setBidInviteGroupStatus(
  inviteIds: string[],
  status: BidInviteStatus
): Promise<void> {
  for (const id of inviteIds) {
    await apiFetch(`/bid-invites/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    });
  }
  revalidateInviteSurfaces();
}
