"use server";

import { revalidatePath } from "next/cache";
import { apiFetch, type WebMentionsResponse } from "@/lib/api";

const REFRESH_TIMEOUT_MS = 30_000;

export async function refreshWebMentions(formData: FormData): Promise<void> {
  const oppId = String(formData.get("opportunity_id") ?? "");
  if (!oppId) throw new Error("missing opportunity_id");
  await apiFetch<WebMentionsResponse>(
    `/opportunities/${oppId}/web-mentions/refresh`,
    {
      method: "POST",
      timeoutMs: REFRESH_TIMEOUT_MS
    }
  );
  revalidatePath(`/opportunities/${oppId}`);
}
