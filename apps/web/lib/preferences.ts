"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";

const HOW_IT_WORKS_COOKIE = "mactech.dismiss.howitworks";
const COOKIE_TTL_DAYS = 365;

export async function dismissHowItWorks(): Promise<void> {
  const c = await cookies();
  c.set(HOW_IT_WORKS_COOKIE, "1", {
    path: "/",
    maxAge: 60 * 60 * 24 * COOKIE_TTL_DAYS,
    httpOnly: false,
    sameSite: "lax"
  });
  revalidatePath("/dashboard");
}

export async function showHowItWorks(): Promise<void> {
  const c = await cookies();
  c.delete(HOW_IT_WORKS_COOKIE);
  revalidatePath("/dashboard");
}
