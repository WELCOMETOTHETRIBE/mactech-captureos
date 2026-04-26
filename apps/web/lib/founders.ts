"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { apiFetch, type FounderRecord } from "@/lib/api";

const PILLAR_OPTIONS = [
  "security",
  "infrastructure",
  "quality",
  "governance",
  "other"
] as const;

function _readPillar(formData: FormData): string {
  const v = String(formData.get("pillar") ?? "other").trim().toLowerCase();
  return (PILLAR_OPTIONS as readonly string[]).includes(v) ? v : "other";
}

export async function createFounder(formData: FormData): Promise<void> {
  const body = {
    full_name: String(formData.get("full_name") ?? "").trim(),
    title: String(formData.get("title") ?? "").trim(),
    pillar: _readPillar(formData),
    email: String(formData.get("email") ?? "").trim() || null,
    bio: String(formData.get("bio") ?? "").trim() || null,
    digest_enabled: formData.get("digest_enabled") === "on"
  };
  if (!body.full_name || !body.title) {
    throw new Error("Name and title are required.");
  }
  await apiFetch<FounderRecord>("/founders", {
    method: "POST",
    body: JSON.stringify(body)
  });
  revalidatePath("/settings");
  revalidatePath("/onboarding");
  redirect("/settings");
}

export async function updateFounder(
  founderId: string,
  formData: FormData
): Promise<void> {
  const email = String(formData.get("email") ?? "").trim();
  const body: Record<string, unknown> = {
    full_name: String(formData.get("full_name") ?? "").trim(),
    title: String(formData.get("title") ?? "").trim(),
    pillar: _readPillar(formData),
    bio: String(formData.get("bio") ?? "").trim() || null,
    digest_enabled: formData.get("digest_enabled") === "on"
  };
  if (email.length === 0) {
    body.clear_email = true;
  } else {
    body.email = email;
  }
  await apiFetch<FounderRecord>(`/founders/${founderId}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  revalidatePath("/settings");
  revalidatePath("/onboarding");
  redirect("/settings");
}

export async function deleteFounder(formData: FormData): Promise<void> {
  const id = String(formData.get("id") ?? "");
  if (!id) throw new Error("missing id");
  await apiFetch<void>(`/founders/${id}`, { method: "DELETE" });
  revalidatePath("/settings");
  revalidatePath("/onboarding");
}
