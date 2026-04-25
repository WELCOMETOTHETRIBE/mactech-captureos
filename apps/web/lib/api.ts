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
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status} on ${path}: ${body.slice(0, 200)}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

/* ── /me ─────────────────────────────────────────────────────────── */

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

/* ── /me/dashboard ───────────────────────────────────────────────── */

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

/* ── /opportunities (list) ──────────────────────────────────────── */

export type OpportunityListItem = {
  id: string;
  notice_id: string;
  title: string;
  notice_type: string | null;
  set_aside: string | null;
  naics_code: string | null;
  agency_short: string | null;
  posted_at: string | null;
  response_deadline: string | null;
  days_until_deadline: number | null;
  score: number | null;
  why_it_matters: string | null;
  incumbent_summary: string | null;
  assigned_founder_slug: string | null;
};

export type OpportunityListResponse = {
  page: number;
  limit: number;
  total: number;
  has_next: boolean;
  items: OpportunityListItem[];
  facets: {
    set_asides: Record<string, number>;
    notice_types: Record<string, number>;
    naics: Record<string, number>;
    assigned_founder: Record<string, number>;
  };
};

/* ── /opportunities/{id} (detail) ───────────────────────────────── */

export type CapabilityMatch = {
  id: string;
  title: string;
  summary: string;
  similarity: number;
};

export type IncumbentExclusionsBlock = {
  uei: string;
  is_excluded: boolean;
  checked_at: string;
  cache_status: "fresh" | "stale" | string;
};

export type IncumbentBlock = {
  uei: string | null;
  name: string | null;
  contract_id: string | null;
  contract_end_date: string | null;
  contract_amount: number | null;
  exclusions: IncumbentExclusionsBlock | null;
};

export type ScoreBlock = {
  score: number;
  breakdown: Record<string, number>;
  assigned_founder_slug: string | null;
  why_it_matters: string | null;
  why_it_matters_model: string | null;
  scored_at: string | null;
};

export type DescriptionBlock = {
  text: string | null;
  source_url: string | null;
  fetch_status: "fetched" | "pending" | "unavailable" | string;
};

export type OpportunityHeader = {
  id: string;
  notice_id: string;
  title: string;
  notice_type: string | null;
  set_aside: string | null;
  set_aside_description: string | null;
  naics_code: string | null;
  agency: string | null;
  solicitation_number: string | null;
  posted_at: string | null;
  response_deadline: string | null;
  days_until_deadline: number | null;
  sam_link: string | null;
  additional_info_link: string | null;
};

export type OpportunityDetail = {
  opportunity: OpportunityHeader;
  description: DescriptionBlock;
  incumbent: IncumbentBlock | null;
  score: ScoreBlock | null;
  capability_matches: CapabilityMatch[];
  enrichment_notes: string | null;
  enriched_at: string | null;
  sam_resource_links: string[];
};

/* ── /capability-statements ─────────────────────────────────────── */

export type CapabilityFounderRef = {
  slug: string;
  full_name: string;
  pillar: string;
};

export type CapabilityStatementOut = {
  id: string;
  slug: string;
  title: string;
  summary: string;
  related_naics: string[];
  related_founders: CapabilityFounderRef[];
  has_embedding: boolean;
  created_at: string;
  updated_at: string;
};

export type CapabilityStatementsResponse = {
  total: number;
  items: CapabilityStatementOut[];
};

/* ── /me/settings ───────────────────────────────────────────────── */

export type TenantOut = {
  id: string;
  slug: string;
  name: string;
  plan: string;
  uei: string | null;
  cage_code: string | null;
  clerk_org_id: string | null;
};

export type FounderOut = {
  slug: string;
  full_name: string;
  title: string;
  pillar: string;
  email: string | null;
  digest_enabled: boolean;
};

export type NaicsRow = {
  code: string;
  title: string;
  tier: string | null;
  founder_slugs: string[];
};

export type SavedSearchOut = {
  id: string;
  name: string;
  owner_founder_slug: string | null;
  alert_threshold: number;
  alert_cadence: string;
  alert_channels: string[];
  naics_codes: string[];
  set_asides: string[];
  keywords: string[];
  created_at: string;
};

export type SettingsResponse = {
  tenant: TenantOut;
  founders: FounderOut[];
  naics: NaicsRow[];
  saved_searches: SavedSearchOut[];
};

/* ── /pursuits (capture pipeline kanban) ────────────────────────── */

export type PursuitStage =
  | "lead"
  | "qualify"
  | "pursue"
  | "propose"
  | "submit"
  | "won"
  | "lost";

export const PURSUIT_STAGES_ORDER: PursuitStage[] = [
  "lead",
  "qualify",
  "pursue",
  "propose",
  "submit",
  "won",
  "lost"
];

export type PursuitOpp = {
  id: string;
  notice_id: string;
  title: string;
  notice_type: string | null;
  set_aside: string | null;
  naics_code: string | null;
  agency_short: string | null;
  posted_at: string | null;
  response_deadline: string | null;
  days_until_deadline: number | null;
  score: number | null;
};

export type PursuitCard = {
  id: string;
  stage: PursuitStage;
  owner_founder_slug: string | null;
  owner_founder_name: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  last_stage_change_at: string;
  days_in_stage: number;
  opportunity: PursuitOpp;
};

export type StageColumn = {
  stage: PursuitStage;
  label: string;
  count: number;
  cards: PursuitCard[];
};

export type KanbanResponse = {
  rendered_at: string;
  total: number;
  by_owner: Record<string, number>;
  columns: StageColumn[];
};
