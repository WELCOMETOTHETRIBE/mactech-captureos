"use server";

import { revalidatePath } from "next/cache";
import { apiFetch } from "@/lib/api";

/**
 * Server actions for triggering Apify kicks on demand. Useful for
 * verifying a config fix without waiting for the next 0530 ET beat.
 */

export async function triggerForecastsRun(): Promise<void> {
  await apiFetch<unknown>(
    "/me/integrations/apify/forecasts/trigger",
    { method: "POST", body: "{}" }
  );
  revalidatePath("/forecasts");
}

export async function triggerIndustryDaysRun(): Promise<void> {
  await apiFetch<unknown>(
    "/me/integrations/apify/industry-days/trigger",
    { method: "POST", body: "{}" }
  );
  revalidatePath("/events");
}
