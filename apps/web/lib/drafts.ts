"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { apiFetch, type DraftOut, type DraftStatus } from "@/lib/api";

export async function updateDraftContent(
  draftId: string,
  formData: FormData
): Promise<void> {
  const content = String(formData.get("content") ?? "");
  const title = String(formData.get("title") ?? "").trim();
  if (!content.trim()) {
    throw new Error("Draft content cannot be empty.");
  }
  const body: Record<string, unknown> = { content };
  if (title) body.title = title;
  await apiFetch<DraftOut>(`/drafts/${draftId}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  revalidatePath(`/drafts/${draftId}`);
  revalidatePath("/drafts");
}

export async function setDraftStatus(formData: FormData): Promise<void> {
  const id = String(formData.get("id") ?? "");
  const status = String(formData.get("status") ?? "") as DraftStatus;
  if (!id) throw new Error("missing draft id");
  await apiFetch<DraftOut>(`/drafts/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
  revalidatePath(`/drafts/${id}`);
  revalidatePath("/drafts");
}

export async function deleteDraft(formData: FormData): Promise<void> {
  const id = String(formData.get("id") ?? "");
  const oppId = String(formData.get("opportunity_id") ?? "");
  const redirectTo = String(formData.get("redirect_to") ?? "/drafts");
  if (!id) throw new Error("missing draft id");
  await apiFetch<void>(`/drafts/${id}`, { method: "DELETE" });
  revalidatePath("/drafts");
  if (oppId) revalidatePath(`/opportunities/${oppId}`);
  redirect(redirectTo);
}
