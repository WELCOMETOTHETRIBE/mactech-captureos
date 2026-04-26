"use server";

import { apiFetch, type SearchResponse } from "@/lib/api";

const SEARCH_TIMEOUT_MS = 6_000;

/**
 * Global search server action — used by the Cmd-K modal.
 * Empty query returns "recent" results per kind.
 */
export async function searchEverything(query: string): Promise<SearchResponse> {
  const q = query.trim().slice(0, 120);
  const params = new URLSearchParams();
  if (q.length > 0) params.set("q", q);
  params.set("limit", "8");
  return apiFetch<SearchResponse>(
    `/search${params.toString() ? "?" + params.toString() : ""}`,
    { timeoutMs: SEARCH_TIMEOUT_MS }
  );
}
