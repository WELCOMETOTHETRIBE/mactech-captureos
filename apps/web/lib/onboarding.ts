"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import {
  apiFetch,
  type OnboardingTenantHeaderOut,
  type SamEntityProfile
} from "@/lib/api";

const SAM_TIMEOUT_MS = 30_000;

/**
 * Server actions for the /onboarding wizard. The SAM Entity lookup
 * goes through the API (server-side) so the SAM API key never reaches
 * the browser.
 */

export async function lookupSamEntity(uei: string): Promise<SamEntityProfile> {
  const cleaned = uei.trim().toUpperCase();
  if (cleaned.length < 6) {
    throw new Error("UEI looks too short.");
  }
  return apiFetch<SamEntityProfile>(
    `/onboarding/sam-entity/${encodeURIComponent(cleaned)}`,
    { timeoutMs: SAM_TIMEOUT_MS }
  );
}

/**
 * Save firm details from the wizard. Form fields:
 *   uei (text)
 *   cage_code (text)
 *   legal_name (text)
 *   set_aside_certifications (multi-checkbox; collected via formData.getAll)
 *   complete (hidden flag — when "1", also flip onboarding_completed_at)
 */
export async function saveFirmDetails(formData: FormData): Promise<void> {
  const certs = formData
    .getAll("set_aside_certifications")
    .map((v) => String(v).trim())
    .filter((v) => v.length > 0);

  // target_naics arrives via two channels: explicit checkboxes
  // (multi-checkbox value="<code>") + an optional "extra naics" text field
  // for codes not in the suggested set.
  const naicsCheckboxes = formData
    .getAll("target_naics")
    .map((v) => String(v).trim())
    .filter((v) => /^\d{2,8}$/.test(v));
  const naicsExtra = String(formData.get("target_naics_extra") ?? "")
    .split(",")
    .map((v) => v.trim())
    .filter((v) => /^\d{2,8}$/.test(v));
  const naicsAll = Array.from(new Set([...naicsCheckboxes, ...naicsExtra]));
  // The form always submits naics inputs; we treat any submission as an
  // explicit set. To clear the override, the user submits with no checkboxes
  // checked AND an empty extra field — that produces an empty array which
  // the API treats as "clear".
  const wantsNaicsUpdate =
    formData.has("target_naics") || formData.has("target_naics_extra");

  const body: Record<string, unknown> = {
    uei: (String(formData.get("uei") ?? "").trim() || null),
    cage_code: (String(formData.get("cage_code") ?? "").trim() || null),
    legal_name: (String(formData.get("legal_name") ?? "").trim() || null),
    set_aside_certifications: certs
  };
  if (wantsNaicsUpdate) body.target_naics = naicsAll;

  await apiFetch<OnboardingTenantHeaderOut>(
    "/me/onboarding/firm-details",
    {
      method: "POST",
      body: JSON.stringify(body)
    }
  );

  if (String(formData.get("complete") ?? "") === "1") {
    await apiFetch<OnboardingTenantHeaderOut>(
      "/me/onboarding/complete",
      { method: "POST", body: JSON.stringify({}) }
    );
    revalidatePath("/onboarding");
    revalidatePath("/dashboard");
    revalidatePath("/settings");
    redirect("/dashboard");
  }

  revalidatePath("/onboarding");
  revalidatePath("/dashboard");
  revalidatePath("/settings");
}

export async function resetOnboarding(): Promise<void> {
  await apiFetch<OnboardingTenantHeaderOut>(
    "/me/onboarding/reset",
    { method: "POST", body: JSON.stringify({}) }
  );
  revalidatePath("/dashboard");
  revalidatePath("/settings");
  revalidatePath("/onboarding");
  redirect("/onboarding");
}

/**
 * Two-stage form action used by the "Look up UEI" button. Reads the
 * UEI value out of the form, calls the API, then redirects to a
 * version of the same page with the prefill query params populated.
 */
export async function lookupAndPrefill(formData: FormData): Promise<void> {
  const uei = String(formData.get("uei") ?? "").trim().toUpperCase();
  if (!uei) {
    throw new Error("Type a UEI to look up.");
  }
  let profile: SamEntityProfile;
  try {
    profile = await lookupSamEntity(uei);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    redirect(
      `/onboarding?uei=${encodeURIComponent(uei)}&error=${encodeURIComponent(
        msg.slice(0, 200)
      )}`
    );
  }

  const params = new URLSearchParams({
    uei: profile.uei,
    legal_name: profile.legal_business_name ?? "",
    cage_code: profile.cage_code ?? "",
    set_asides: profile.set_aside_short_codes.join(","),
    naics: profile.naics_codes.slice(0, 6).join(",")
  });
  redirect(`/onboarding?${params.toString()}`);
}
