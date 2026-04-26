"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import {
  apiFetch,
  type CapabilityStatementOut,
  type PastPerformanceOut,
  type PastPerformanceRole,
  type TeamingPartnerOut,
  type TeamingPartnerStatus
} from "@/lib/api";

/**
 * Server actions for the past-performance + teaming-partners catalogues.
 * Each form posts a FormData; the action parses it, calls the API, and
 * revalidates /library before redirecting back.
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

function readOptDate(formData: FormData, key: string): string | null {
  const raw = String(formData.get(key) ?? "").trim();
  return raw.length > 0 ? raw : null;
}

function readOptNumber(formData: FormData, key: string): number | null {
  const raw = String(formData.get(key) ?? "").trim();
  if (raw.length === 0) return null;
  const n = Number(raw.replace(/[$,]/g, ""));
  return Number.isFinite(n) ? n : null;
}

/* ── past performance ───────────────────────────────────────────── */

export async function createPastPerformance(formData: FormData): Promise<void> {
  const body = {
    title: String(formData.get("title") ?? "").trim(),
    customer_agency: readOptString(formData, "customer_agency"),
    customer_office: readOptString(formData, "customer_office"),
    contract_number: readOptString(formData, "contract_number"),
    role: (String(formData.get("role") ?? "prime") as PastPerformanceRole),
    period_start: readOptDate(formData, "period_start"),
    period_end: readOptDate(formData, "period_end"),
    contract_value: readOptNumber(formData, "contract_value"),
    naics_code: readOptString(formData, "naics_code"),
    summary: String(formData.get("summary") ?? "").trim(),
    keywords: readArray(formData, "keywords"),
    related_capability_slugs: readArray(formData, "related_capability_slugs"),
    related_founder_slugs: readArray(formData, "related_founder_slugs")
  };
  if (!body.title || !body.summary) {
    throw new Error("Title and summary are required.");
  }
  await apiFetch<PastPerformanceOut>("/past-performance", {
    method: "POST",
    body: JSON.stringify(body)
  });
  revalidatePath("/library");
  redirect("/library");
}

export async function updatePastPerformance(
  ppId: string,
  formData: FormData
): Promise<void> {
  const body: Record<string, unknown> = {
    title: String(formData.get("title") ?? "").trim(),
    customer_agency: readOptString(formData, "customer_agency"),
    customer_office: readOptString(formData, "customer_office"),
    contract_number: readOptString(formData, "contract_number"),
    role: String(formData.get("role") ?? "prime") as PastPerformanceRole,
    naics_code: readOptString(formData, "naics_code"),
    summary: String(formData.get("summary") ?? "").trim(),
    keywords: readArray(formData, "keywords"),
    related_capability_slugs: readArray(formData, "related_capability_slugs"),
    related_founder_slugs: readArray(formData, "related_founder_slugs")
  };
  const ps = readOptDate(formData, "period_start");
  const pe = readOptDate(formData, "period_end");
  const cv = readOptNumber(formData, "contract_value");
  if (ps === null) body.clear_period_start = true;
  else body.period_start = ps;
  if (pe === null) body.clear_period_end = true;
  else body.period_end = pe;
  if (cv === null) body.clear_contract_value = true;
  else body.contract_value = cv;

  await apiFetch<PastPerformanceOut>(`/past-performance/${ppId}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  revalidatePath("/library");
  redirect("/library");
}

export async function deletePastPerformance(formData: FormData): Promise<void> {
  const id = String(formData.get("id") ?? "");
  if (!id) throw new Error("missing id");
  await apiFetch<void>(`/past-performance/${id}`, { method: "DELETE" });
  revalidatePath("/library");
}

/* ── teaming partners ──────────────────────────────────────────── */

export async function createTeamingPartner(formData: FormData): Promise<void> {
  const email = readOptString(formData, "contact_email");
  const body = {
    name: String(formData.get("name") ?? "").trim(),
    uei: readOptString(formData, "uei"),
    cage_code: readOptString(formData, "cage_code"),
    capabilities: readArray(formData, "capabilities"),
    naics_codes: readArray(formData, "naics_codes"),
    set_aside_certifications: readArray(formData, "set_aside_certifications"),
    contact_name: readOptString(formData, "contact_name"),
    contact_email: email,
    notes: readOptString(formData, "notes"),
    status: (String(formData.get("status") ?? "active") as TeamingPartnerStatus)
  };
  if (!body.name) {
    throw new Error("Partner name is required.");
  }
  await apiFetch<TeamingPartnerOut>("/teaming-partners", {
    method: "POST",
    body: JSON.stringify(body)
  });
  revalidatePath("/library");
  redirect("/library");
}

export async function updateTeamingPartner(
  partnerId: string,
  formData: FormData
): Promise<void> {
  const email = readOptString(formData, "contact_email");
  const body: Record<string, unknown> = {
    name: String(formData.get("name") ?? "").trim(),
    uei: readOptString(formData, "uei"),
    cage_code: readOptString(formData, "cage_code"),
    capabilities: readArray(formData, "capabilities"),
    naics_codes: readArray(formData, "naics_codes"),
    set_aside_certifications: readArray(formData, "set_aside_certifications"),
    contact_name: readOptString(formData, "contact_name"),
    notes: readOptString(formData, "notes"),
    status: String(formData.get("status") ?? "active") as TeamingPartnerStatus
  };
  if (email === null) body.clear_contact_email = true;
  else body.contact_email = email;

  await apiFetch<TeamingPartnerOut>(`/teaming-partners/${partnerId}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  revalidatePath("/library");
  redirect("/library");
}

export async function deleteTeamingPartner(formData: FormData): Promise<void> {
  const id = String(formData.get("id") ?? "");
  if (!id) throw new Error("missing id");
  await apiFetch<void>(`/teaming-partners/${id}`, { method: "DELETE" });
  revalidatePath("/library");
}

export async function toggleTeamingPartnerStatus(
  formData: FormData
): Promise<void> {
  const id = String(formData.get("id") ?? "");
  const next = String(formData.get("next_status") ?? "");
  if (!id || (next !== "active" && next !== "inactive")) {
    throw new Error("invalid toggle");
  }
  await apiFetch<TeamingPartnerOut>(`/teaming-partners/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status: next })
  });
  revalidatePath("/library");
}

/* ── capability statements ───────────────────────────────────────── */

export async function createCapabilityStatement(formData: FormData): Promise<void> {
  const body = {
    title: String(formData.get("title") ?? "").trim(),
    summary: String(formData.get("summary") ?? "").trim(),
    keywords: readArray(formData, "keywords"),
    related_naics: readArray(formData, "related_naics"),
    related_founder_slugs: readArray(formData, "related_founder_slugs")
  };
  if (!body.title || !body.summary) {
    throw new Error("Title and summary are required.");
  }
  await apiFetch<CapabilityStatementOut>("/capability-statements", {
    method: "POST",
    body: JSON.stringify(body)
  });
  revalidatePath("/library");
  redirect("/library");
}

export async function updateCapabilityStatement(
  csId: string,
  formData: FormData
): Promise<void> {
  const body = {
    title: String(formData.get("title") ?? "").trim(),
    summary: String(formData.get("summary") ?? "").trim(),
    keywords: readArray(formData, "keywords"),
    related_naics: readArray(formData, "related_naics"),
    related_founder_slugs: readArray(formData, "related_founder_slugs")
  };
  await apiFetch<CapabilityStatementOut>(
    `/capability-statements/${csId}`,
    {
      method: "PATCH",
      body: JSON.stringify(body)
    }
  );
  revalidatePath("/library");
  redirect("/library");
}

export async function deleteCapabilityStatement(formData: FormData): Promise<void> {
  const id = String(formData.get("id") ?? "");
  if (!id) throw new Error("missing id");
  await apiFetch<void>(`/capability-statements/${id}`, { method: "DELETE" });
  revalidatePath("/library");
}
