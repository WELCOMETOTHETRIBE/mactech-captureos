"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import {
  apiFetch,
  type DirectoryContactOut,
  type DirectoryOrganizationOut
} from "@/lib/api";

/**
 * Server actions for the shared company directory (bizops-backed). Same shape
 * as library-actions: parse the FormData, call the API, revalidate, redirect.
 */

function readArray(formData: FormData, key: string): string[] {
  const raw = String(formData.get(key) ?? "");
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

function readOptString(formData: FormData, key: string): string | null {
  const raw = String(formData.get(key) ?? "").trim();
  return raw.length > 0 ? raw : null;
}

export async function createDirectoryContact(formData: FormData): Promise<void> {
  const body = {
    name: String(formData.get("name") ?? "").trim(),
    kind: String(formData.get("kind") ?? "EXTERNAL"),
    title: readOptString(formData, "title"),
    department: readOptString(formData, "department"),
    organization_id: readOptString(formData, "organization_id"),
    organization_name: readOptString(formData, "organization_name"),
    email: readOptString(formData, "email"),
    phone: readOptString(formData, "phone"),
    mobile: readOptString(formData, "mobile"),
    linkedin_url: readOptString(formData, "linkedin_url"),
    tags: readArray(formData, "tags"),
    notes: readOptString(formData, "notes")
  };
  if (!body.name) {
    throw new Error("Name is required.");
  }
  await apiFetch<DirectoryContactOut>("/directory/contacts", {
    method: "POST",
    body: JSON.stringify(body)
  });
  revalidatePath("/directory");
  redirect("/directory");
}

export async function createDirectoryOrganization(formData: FormData): Promise<void> {
  const body = {
    name: String(formData.get("name") ?? "").trim(),
    org_type: String(formData.get("org_type") ?? "OTHER"),
    abbreviation: readOptString(formData, "abbreviation"),
    website: readOptString(formData, "website"),
    email: readOptString(formData, "email"),
    phone: readOptString(formData, "phone"),
    uei: readOptString(formData, "uei"),
    cage_code: readOptString(formData, "cage_code"),
    tags: readArray(formData, "tags"),
    notes: readOptString(formData, "notes")
  };
  if (!body.name) {
    throw new Error("Name is required.");
  }
  await apiFetch<DirectoryOrganizationOut>("/directory/organizations", {
    method: "POST",
    body: JSON.stringify(body)
  });
  revalidatePath("/directory");
  redirect("/directory");
}
