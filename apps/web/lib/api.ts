import { auth } from "@clerk/nextjs/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * Server-side fetch helper that grabs a Clerk session token signed with the
 * `mactech` template, attaches it as a Bearer header, and calls the FastAPI
 * backend. Use only from server components / route handlers.
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    throw new Error("apiFetch called without a Clerk session — guard the route");
  }
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    cache: "no-store"
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status} on ${path}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export type FounderHeader = {
  slug: string;
  full_name: string;
  title: string;
  pillar: string;
  email: string | null;
};

export type TenantHeader = {
  slug: string;
  name: string;
  plan: string;
};

export type MeResponse = {
  user_id: string;
  user_email: string;
  founder: FounderHeader | null;
  tenant: TenantHeader;
};

export type TopOpportunity = {
  id: string;
  title: string;
  notice_type: string | null;
  set_aside: string | null;
  naics_code: string | null;
  agency_short: string | null;
  posted_at: string | null;
  response_deadline: string | null;
  score: number;
  why_it_matters: string | null;
  incumbent_name: string | null;
  incumbent_amount: number | null;
  sam_link: string | null;
  detail_url: string;
};

export type FounderCard = {
  slug: string;
  full_name: string;
  pillar: string;
  high_score_count: number;
};

export type DashboardKpis = {
  opportunities_total: number;
  opportunities_last_24h: number;
  scored_above_60: number;
  enriched_with_incumbent: number;
};

export type DashboardResponse = {
  rendered_at: string;
  you: FounderHeader | null;
  your_top: TopOpportunity[];
  pillar_cards: FounderCard[];
  kpis: DashboardKpis;
};
