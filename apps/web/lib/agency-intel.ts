"use server";

import { revalidatePath } from "next/cache";
import { apiFetch, type AgencyIntelOut } from "@/lib/api";

const PULL_TIMEOUT_MS = 30_000;

/**
 * Force a fresh USASpending fetch for the agency intel card. The GET
 * endpoint is read-through cached (7-day TTL); calling it from a
 * server action with a long timeout effectively "pulls" the data.
 *
 * The page-level GET uses a short timeout so cache misses don't block
 * the detail render; this action is the user-triggered escape hatch
 * when that short-timeout fetch fails.
 */
export async function pullAgencyIntel(opportunityId: string): Promise<void> {
  await apiFetch<AgencyIntelOut>(
    `/opportunities/${opportunityId}/agency-intel`,
    { timeoutMs: PULL_TIMEOUT_MS }
  );
  revalidatePath(`/opportunities/${opportunityId}`);
}
