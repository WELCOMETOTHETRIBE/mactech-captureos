import { auth } from "@clerk/nextjs/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * Server-side fetch helper that grabs a Clerk session token signed with the
 * `mactech` template, attaches it as a Bearer header, and calls the FastAPI
 * backend. Use only from server components / route handlers.
 */
export async function apiFetch<T>(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {}
): Promise<T> {
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

  // Most calls finish in <1s; LLM generations (Sources Sought drafter) take
  // 20-60s. Caller can override via init.timeoutMs.
  const timeoutMs = init.timeoutMs ?? 15_000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      cache: "no-store",
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
  }
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
  uei: string | null;
  cage_code: string | null;
  set_aside_certifications: string[];
  target_naics: string[];
  onboarding_completed_at: string | null;
  sprs_score: number | null;
  sprs_max: number;
  sprs_assessment_date: string | null;
  sprs_source_url: string | null;
  sprs_synced_at: string | null;
};

/* ── /founders ───────────────────────────────────────────────────── */

export type FounderRecord = {
  id: string;
  slug: string;
  full_name: string;
  title: string;
  pillar: string;
  bio: string | null;
  email: string | null;
  digest_enabled: boolean;
  created_at: string;
};

export type FoundersListResponse = {
  total: number;
  items: FounderRecord[];
};

/* ── /onboarding ─────────────────────────────────────────────────── */

export type SamEntityProfile = {
  uei: string;
  cage_code: string | null;
  legal_business_name: string | null;
  dba_name: string | null;
  registration_status: string | null;
  registration_date: string | null;
  expiration_date: string | null;
  physical_address_city: string | null;
  physical_address_state: string | null;
  physical_address_country: string | null;
  primary_naics: string | null;
  naics_codes: string[];
  business_types_raw: string[];
  set_aside_short_codes: string[];
  pop_email: string | null;
  pop_first_name: string | null;
  pop_last_name: string | null;
  pop_title: string | null;
};

export type OnboardingTenantHeaderOut = {
  id: string;
  slug: string;
  name: string;
  plan: string;
  uei: string | null;
  cage_code: string | null;
  set_aside_certifications: string[];
  target_naics: string[];
  onboarding_completed_at: string | null;
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
  // Parallel high-moat track — null when the track hasn't scored this
  // opp yet. is_sweet_spot fires when the high-moat scorer flags
  // it as a high-probability easy win (HPEW).
  high_moat_score: number | null;
  is_sweet_spot: boolean;
  // Claude-generated one-sentence scope summary. Populated by the
  // post-score worker chain for every score ≥ 60 opp. When present, the
  // UI promotes this to the primary list title and demotes the raw SAM
  // text to a muted second line.
  scope_one_sentence: string | null;
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
  your_high_fit_open: number;
  your_deadlines_lt_7d: number;
  your_active_pursuits: number;
  drafts_awaiting_review: number;
  // Sweet-spot count: high-probability easy wins (HPEW) assigned to me
  // and not yet in the pipeline. Drives the slot-1 Move in
  // <TodaysMoves /> when > 0.
  your_sweet_spots_open: number;
  your_cyber_scope_alerts: number;
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
  // Parallel high-moat track. Null when the track hasn't scored this
  // opp yet; the row falls back to the general score sort key.
  high_moat_score: number | null;
  // True when the high-moat scorer flagged this as a High-Probability
  // Easy Win. Drives the gold left-border row treatment + HpewBadge.
  is_sweet_spot: boolean;
  // Claude-generated one-sentence scope summary, populated by the
  // post-score worker chain for every score ≥ 60 opp. When present, the
  // UI promotes this above the raw SAM title.
  scope_one_sentence: string | null;
  cyber_scope_score: number | null;
  cyber_scope_likelihood: string | null;
  cyber_scope_pursuit_model: string | null;
  cyber_scope_analysis_id: string | null;
  cyber_scope_attachments_pending: boolean;
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

/**
 * Parallel high-moat (UFGS 25 / FRCS cyber) score block. Null on the
 * parent ScoreBlock when the tenant has no high_moat_scoring config or
 * the opportunity hasn't been re-scored since the column was added.
 *
 * Drives the "Why this is high-moat" strip on the detail page when
 * `score >= 70` (per pass-2 brief §11 Q1). Mirrors the API shape
 * exactly — see apps/api/src/mactech_api/routes/opportunities.py
 * HighMoatBlock for the source-of-truth field set.
 */
export type HighMoatBlock = {
  score: number;
  breakdown: Record<string, number>;
  is_high_probability_easy_win: boolean;
  clause_hits: string[];
  clearance_hits: string[];
  role_hits: string[];
  top_clearance: string; // 'TS_SCI' | 'TS' | 'S' | 'NONE'
  why_it_matters_seed: string | null;
};

export type ScoreBlock = {
  score: number;
  breakdown: Record<string, number>;
  assigned_founder_slug: string | null;
  why_it_matters: string | null;
  why_it_matters_model: string | null;
  scored_at: string | null;
  // Parallel high-moat track. Populated when the tenant has a
  // high_moat_scoring config + the opp has been re-scored since the
  // column landed. The detail page renders the "Why this is high-moat"
  // strip when this is non-null AND `score >= 70`.
  high_moat: HighMoatBlock | null;
  cyber_scope: CyberScopeBlock | null;
};

export type CyberScopeBlock = {
  score: number;
  likelihood: string;
  pursuit_model: string;
  ufgs_center_of_gravity: boolean;
  ufgs_tier_1_hit: boolean;
  top_ufgs_sections: string[];
  top_signals: Array<Record<string, unknown>>;
  scan_pass: string;
  attachments_pending: boolean;
  analysis_id: string | null;
  analysis_url: string | null;
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
  keywords: string[];
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
  sprs_score: number | null;
  sprs_max: number;
  sprs_assessment_date: string | null;
  sprs_source_url: string | null;
  sprs_synced_at: string | null;
};

export type FounderOut = {
  id: string;
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

/* ── /past-performance ──────────────────────────────────────────── */

export type PastPerformanceRole = "prime" | "sub" | "joint_venture" | "individual";
export const PAST_PERFORMANCE_ROLES_ORDER: PastPerformanceRole[] = [
  "prime",
  "sub",
  "joint_venture",
  "individual"
];

export type PastPerformanceOut = {
  id: string;
  title: string;
  customer_agency: string | null;
  customer_office: string | null;
  contract_number: string | null;
  role: PastPerformanceRole;
  period_start: string | null;
  period_end: string | null;
  contract_value: number | null;
  naics_code: string | null;
  summary: string;
  keywords: string[];
  related_capability_slugs: string[];
  related_founder_slugs: string[];
  created_at: string;
  updated_at: string;
};

export type PastPerformanceList = {
  total: number;
  items: PastPerformanceOut[];
};

/* ── /teaming-partners ──────────────────────────────────────────── */

export type TeamingPartnerStatus = "active" | "inactive";

export type TeamingPartnerOut = {
  id: string;
  name: string;
  uei: string | null;
  cage_code: string | null;
  capabilities: string[];
  naics_codes: string[];
  set_aside_certifications: string[];
  contact_name: string | null;
  contact_email: string | null;
  notes: string | null;
  status: TeamingPartnerStatus;
  created_at: string;
  updated_at: string;
};

export type TeamingPartnerList = {
  total: number;
  active_count: number;
  items: TeamingPartnerOut[];
};

/* ── /drafts ────────────────────────────────────────────────────── */

export type DraftStatus = "draft" | "reviewed" | "submitted" | "archived";
export type DraftType =
  | "sources_sought"
  | "rfp_response"
  | "compliance_matrix"
  | "white_paper";

export const DRAFT_STATUS_ORDER: DraftStatus[] = [
  "draft",
  "reviewed",
  "submitted",
  "archived"
];

export type DraftOpp = {
  id: string;
  notice_id: string;
  title: string;
  notice_type: string | null;
};

export type DraftFounderRef = {
  slug: string;
  full_name: string;
};

export type DraftOut = {
  id: string;
  opportunity: DraftOpp;
  parent_draft_id: string | null;
  created_by: DraftFounderRef | null;
  draft_type: DraftType;
  title: string;
  content: string;
  status: DraftStatus;
  version: number;
  custom_instructions: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  citations: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type DraftListItem = {
  id: string;
  opportunity: DraftOpp;
  draft_type: DraftType;
  title: string;
  status: DraftStatus;
  version: number;
  model: string | null;
  output_tokens: number | null;
  created_at: string;
  updated_at: string;
};

export type DraftListResponse = {
  total: number;
  items: DraftListItem[];
};

/* ── /explain/{slug} ────────────────────────────────────────────── */

export type TermExplanationResponse = {
  slug: string;
  kind: string;
  label: string;
  summary: string;
  body: string;
  cached: boolean;
  prompt_version: string;
  model: string | null;
};

/* ── /opportunities/{id}/ask + /questions ──────────────────────── */

export type AskerRef = {
  slug: string;
  full_name: string;
};

export type QuestionOut = {
  id: string;
  question: string;
  answer: string;
  starter_kind: string | null;
  asked_by: AskerRef | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
};

export type QuestionListResponse = {
  total: number;
  items: QuestionOut[];
  starters: Record<string, string>;
};

/* ── /search (Cmd-K global search) ─────────────────────────────── */

export type SearchHitKind =
  | "opportunity"
  | "draft"
  | "teaming_partner"
  | "past_performance";

export type SearchHit = {
  kind: SearchHitKind;
  id: string;
  title: string;
  subtitle: string | null;
  score: number | null;
  url: string;
};

export type SearchResponse = {
  query: string;
  total: number;
  hits: SearchHit[];
  grouped: Record<string, SearchHit[]>;
};

/* ── /opportunities/{id}/agency-intel ──────────────────────────── */

export type AgencyIntelTopRecipient = {
  name: string;
  uei: string | null;
  total: number;
  award_count: number;
};

export type AgencyIntelOut = {
  agency_name: string;
  naics_code: string;
  lookback_days: number;
  award_count: number;
  total_obligated: number | null;
  avg_award_value: number | null;
  median_award_value: number | null;
  top_recipients: AgencyIntelTopRecipient[];
  sample_size: number | null;
  refreshed_at: string;
  cache_age_hours: number;
  is_fresh: boolean;
  lookup_failed: boolean;
  failure_note: string | null;
};

/* ── /opportunities/{id}/brief ─────────────────────────────────── */

export type BriefOut = {
  id: string;
  opportunity_id: string;
  scope_one_sentence: string;
  must_have_requirements: string[];
  nice_to_have: string[];
  red_flags_for_small_biz: string[];
  suggested_team_roles: string[];
  model: string | null;
  prompt_version: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  description_chars: number | null;
  created_at: string;
  updated_at: string;
};

/* ── /opportunities/{id}/web-mentions ──────────────────────────── */

export type WebMentionResult = {
  position: number;
  title: string;
  link: string;
  displayed_link: string | null;
  snippet: string | null;
  source: string | null;
  date: string | null;
};

export type WebMentionGroup = {
  kind: "program" | "incumbent" | "agency_news" | string;
  query: string;
  results: WebMentionResult[];
  fetched_at: string | null;
  is_stale: boolean;
};

export type WebMentionsResponse = {
  opportunity_id: string;
  groups: WebMentionGroup[];
  has_serpapi_key: boolean;
};

/* ── /events ───────────────────────────────────────────────────── */

export type AgencyEventOut = {
  id: string;
  title: string;
  agency: string | null;
  kind: string | null;
  starts_at: string | null;
  ends_at: string | null;
  location: string | null;
  source_url: string;
  source_host: string | null;
  registration_url: string | null;
  naics_codes: string[];
  summary: string | null;
  last_seen_at: string;
};

export type AgencyEventsResponse = {
  total: number;
  items: AgencyEventOut[];
};

/* ── /forecasts ────────────────────────────────────────────────── */

export type ForecastOut = {
  id: string;
  title: string;
  agency: string | null;
  contracting_office: string | null;
  description: string | null;
  naics_code: string | null;
  naics_codes: string[];
  set_aside: string | null;
  contract_type: string | null;
  estimated_value_low: number | null;
  estimated_value_high: number | null;
  estimated_value_text: string | null;
  expected_solicitation_date: string | null;
  expected_award_date: string | null;
  period_of_performance_end: string | null;
  incumbent_name: string | null;
  incumbent_contract_number: string | null;
  poc_name: string | null;
  poc_email: string | null;
  source_url: string;
  source_host: string | null;
  last_seen_at: string;
  matches_target_naics: boolean;
  score: number;
  score_breakdown: Record<string, number>;
  assigned_founder_slug: string | null;
  assigned_founder_name: string | null;
  assigned_founder_pillar: string | null;
  incumbent_total_obligations: number | null;
  incumbent_award_count: number | null;
  incumbent_distress_score: number | null;
  incumbent_distress_summary: string | null;
  incumbent_sec_ticker: string | null;
  incumbent_filings_last_90d: number | null;
};

/* ── /me/integrations ──────────────────────────────────────────── */

export type IntegrationRunOut = {
  capability: string;
  last_event_type: string | null;
  apify_status: string | null;
  items_count: number | null;
  ingest_error: string | null;
  received_at: string | null;
  processed_at: string | null;
};

export type IntegrationStatusOut = {
  capability: string;
  label: string;
  description: string;
  schedule: string;
  api_token_var: string;
  api_token_set: boolean;
  last_run: IntegrationRunOut | null;
};

export type IntegrationsResponse = {
  integrations: IntegrationStatusOut[];
};

/* ── /tenant/eligibility ────────────────────────────────────────── */

export type SamRegistrationStatus =
  | "active"
  | "expired"
  | "invalid"
  | "unverified";

export type SamRegistrationOut = {
  status: SamRegistrationStatus;
  registration_date: string | null;
  expires_at: string | null;
  days_until_expiration: number | null;
  last_checked_at: string | null;
};

export type ExclusionsBlock = {
  is_excluded: boolean;
  record_count: number;
  last_checked_at: string | null;
};

export type CyberPostureBlock = {
  sprs_score: number | null;
  sprs_max: number;
  sprs_assessment_date: string | null;
  sprs_synced_at: string | null;
};

export type GovernanceReadinessBlock = {
  accounting_system_dcaa_ready: boolean | null;
  fcl_status: string | null;
  fcl_level: string | null;
  e_verify_enrolled: boolean | null;
  reps_certs_current: boolean | null;
  source: string;
};

export type TenantEligibilityOut = {
  tenant_slug: string;
  uei: string | null;
  cage_code: string | null;
  set_aside_certifications: string[];
  sam_registration: SamRegistrationOut;
  exclusions: ExclusionsBlock;
  cyber: CyberPostureBlock;
  governance: GovernanceReadinessBlock;
  blockers: string[];
  has_hard_blocker: boolean;
};

/* ── /opportunities/{id}/amendments + /pursuits/{id}/audit ───── */

export type AmendmentDiffEntry = {
  field: string;
  before: unknown | null;
  after: unknown | null;
};

export type AmendmentOut = {
  id: string;
  opportunity_id: string;
  previous_hash: string | null;
  new_hash: string;
  previous_response_deadline: string | null;
  new_response_deadline: string | null;
  previous_title: string | null;
  new_title: string | null;
  diff_summary: AmendmentDiffEntry[];
  detected_at: string;
};

export type AmendmentListOut = {
  opportunity_id: string;
  amendments: AmendmentOut[];
};

export type AuditEventOut = {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  actor_user_email: string | null;
  actor_founder_slug: string | null;
  actor_founder_name: string | null;
  actor_label: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AuditTrailOut = {
  pursuit_id: string;
  events: AuditEventOut[];
};

/* ── /pursuits/{id} (detail) ────────────────────────────────────── */

export type PursuitOppLite = {
  id: string;
  notice_id: string;
  title: string;
  agency: string | null;
  naics_code: string | null;
  set_aside: string | null;
  posted_at: string | null;
  response_deadline: string | null;
};

export type LinkedPastPerformance = {
  id: string;
  title: string;
  customer_agency: string | null;
  customer_office: string | null;
  contract_number: string | null;
  role: string | null;
  period_start: string | null;
  period_end: string | null;
  contract_value: number | null;
  summary: string | null;
  sort_order: number;
};

export type LinkedKeyPerson = {
  id: string;
  slug: string;
  full_name: string;
  title: string | null;
  pillar: string | null;
  sort_order: number;
};

export type LinkedTeamingPartner = {
  id: string;
  name: string;
  uei: string | null;
  capabilities: string[];
  naics_codes: string[];
  set_aside_certifications: string[];
  sort_order: number;
};

export type BidDecision = "pending" | "bid" | "no_bid";

export type PursuitDetailOut = {
  id: string;
  stage: PursuitStage;
  notes: string | null;
  win_themes: string[];
  discriminators: string[];
  bid_decision: BidDecision;
  bid_decided_at: string | null;
  bid_decided_by_user_email: string | null;
  bid_rationale: string | null;
  owner_founder_slug: string | null;
  owner_founder_name: string | null;
  created_at: string;
  updated_at: string;
  last_stage_change_at: string;
  opportunity: PursuitOppLite;
  selected_past_performance: LinkedPastPerformance[];
  selected_key_personnel: LinkedKeyPerson[];
  selected_teaming_partners: LinkedTeamingPartner[];
  library_size_past_performance: number;
  library_size_key_personnel: number;
  library_size_teaming_partners: number;
};

export type ForecastsResponse = {
  total: number;
  items: ForecastOut[];
  target_naics_filter: boolean;
  target_naics: string[];
};

/* ── /opportunities/{id}/solicitation-extraction ────────────────── */

export type SolicitationExtractionOut = {
  id: string;
  opportunity_id: string;
  status: string; // pending | running | complete | failed
  description_chars: number | null;
  compliance_count: number;
  requirements_count: number;
  evaluation_count: number;
  model: string | null;
  prompt_version: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type ComplianceItemOut = {
  id: string;
  item_id: string;
  statement: string;
  section_l_citation: string | null;
  pass_fail: boolean;
  notes: string | null;
  sort_order: number;
};

export type ComplianceMatrixOut = {
  extraction_id: string;
  opportunity_id: string;
  items: ComplianceItemOut[];
  last_extracted_at: string;
};

export type RequirementCategory =
  | "technical"
  | "operational"
  | "security"
  | "staffing"
  | "performance"
  | "reporting"
  | "other";

export type RequirementItemOut = {
  id: string;
  item_id: string;
  statement: string;
  source_citation: string | null;
  category: RequirementCategory;
  sort_order: number;
};

export type RequirementsMatrixOut = {
  extraction_id: string;
  opportunity_id: string;
  items: RequirementItemOut[];
  last_extracted_at: string;
};

export type EvaluationPassFailItemOut = {
  id: string;
  statement: string;
  source_citation: string | null;
  sort_order: number;
};

export type EvaluationScoredFactorOut = {
  id: string;
  name: string;
  weight: number | null;
  description: string | null;
  source_citation: string | null;
  sort_order: number;
};

export type EvaluationOut = {
  extraction_id: string;
  opportunity_id: string;
  pass_fail_items: EvaluationPassFailItemOut[];
  scored_factors: EvaluationScoredFactorOut[];
  last_extracted_at: string;
};

/* ── /opportunities/{id}/cyber-summary ──────────────────────────── */

export type CyberPostureSummary = {
  sprs_score: number | null;
  sprs_max: number;
  sprs_assessment_date: string | null;
  sprs_source_url: string | null;
  sprs_synced_at: string | null;
};

export type CyberSummaryOut = {
  opportunity_id: string;
  clauses_identified: string[];
  cmmc_level_required: string | null;
  handles_cui: boolean;
  handles_fci: boolean;
  handles_itar: boolean;
  posture: CyberPostureSummary;
  sufficiency: "sufficient" | "gap" | "unknown";
  sufficiency_notes: string | null;
  // Optional — clauses cited by the solicitation that the tenant has no
  // evidence of meeting yet. UI surface (the "What's missing" sub-rail
  // on <CyberFitCard>) consumes this when populated. Backend currently
  // returns the field absent / empty; the cross-reference logic is a
  // pass-3 endpoint addition. See brief §7.5 and §8.
  missing_clauses?: string[];
};

/* ── /pursuits/{id}/capture-package ─────────────────────────────── */

export type CPOpportunitySection = {
  notice_id: string;
  source: string;
  solicitation_number: string | null;
  title: string;
  notice_type: string | null;
  agency: string | null;
  subagency: string | null;
  office: string | null;
  naics_code: string | null;
  set_aside: string | null;
  contract_type: string | null;
  response_deadline: string | null;
  posted_at: string | null;
  estimated_value_low: number | null;
  estimated_value_high: number | null;
  place_of_performance: Record<string, unknown> | null;
  submission_method: string | null;
  description_url: string | null;
  description_text_excerpt: string | null;
};

export type CPSolicitationFile = {
  file_id: string | null;
  name: string;
  url: string | null;
  kind: string;
  posted_at: string | null;
  sha256: string | null;
};

export type CPSolicitationSection = {
  primary_description_url: string | null;
  primary_description_text_excerpt: string | null;
  files: CPSolicitationFile[];
  amendments: CPSolicitationFile[];
  raw_payload_available: boolean;
};

export type CPComplianceItem = {
  id: string;
  statement: string;
  section_l_citation: string | null;
  pass_fail: boolean;
  notes: string | null;
};

export type CPComplianceMatrixSection = {
  items: CPComplianceItem[];
  source_documents: string[];
  last_generated_at: string | null;
  status: "not_generated" | "generated" | "stale";
};

export type CPRequirementItem = {
  id: string;
  statement: string;
  source_citation: string | null;
  category: RequirementCategory;
};

export type CPRequirementsMatrixSection = {
  items: CPRequirementItem[];
  last_generated_at: string | null;
  status: "not_generated" | "generated" | "stale";
};

export type CPPassFailItem = {
  statement: string;
  source_citation: string | null;
};

export type CPScoredFactor = {
  name: string;
  weight: number | null;
  description: string | null;
  source_citation: string | null;
};

export type CPEvaluationSection = {
  pass_fail_items: CPPassFailItem[];
  scored_factors: CPScoredFactor[];
  status: "not_extracted" | "extracted";
};

export type CPCyberPostureSnapshot = {
  sprs_score: number | null;
  sprs_max: number | null;
  sprs_assessment_date: string | null;
  sprs_source_url: string | null;
  cmmc_level_current: string | null;
  source: "codex" | "stub";
  snapshot_at: string;
};

export type CPCyberSection = {
  clauses_identified: string[];
  cmmc_level_required: string | null;
  handles_cui: boolean | null;
  handles_fci: boolean | null;
  handles_itar: boolean | null;
  posture_snapshot: CPCyberPostureSnapshot | null;
  sufficiency: "sufficient" | "gap" | "unknown";
  sufficiency_notes: string | null;
};

export type CPIncumbentSummary = {
  name: string | null;
  uei: string | null;
  contract_id: string | null;
  end_date: string | null;
  award_amount: number | null;
  cleared_exclusions: boolean | null;
};

export type CPCaptureStrategySection = {
  agency_brief: string | null;
  scope_one_sentence: string | null;
  incumbent: CPIncumbentSummary | null;
  likely_competitors: string[];
  customer_priorities: string | null;
  must_have_requirements: string[];
  nice_to_have: string[];
  red_flags_for_small_biz: string[];
  suggested_team_roles: string[];
};

export type CPWinStrategySection = {
  win_themes: string[];
  discriminators: string[];
};

export type CPPastPerformanceRef = {
  id: string;
  title: string;
  customer_agency: string | null;
  customer_office: string | null;
  contract_number: string | null;
  role: string | null;
  period_start: string | null;
  period_end: string | null;
  contract_value: number | null;
  summary: string | null;
  keywords: string[];
};

export type CPPastPerformanceSection = {
  selected: CPPastPerformanceRef[];
  library_size: number;
  selection_method: "manual" | "ai_suggested" | "none";
};

export type CPKeyPersonRef = {
  id: string;
  slug: string;
  full_name: string;
  title: string | null;
  pillar: string | null;
  bio: string | null;
  email: string | null;
  areas_of_expertise: string[];
};

export type CPKeyPersonnelSection = {
  selected: CPKeyPersonRef[];
  library_size: number;
};

export type CPGovernanceDocState = {
  mnda_executed: boolean | null;
  mnda_signed_at: string | null;
  teaming_agreement_executed: boolean | null;
  teaming_agreement_signed_at: string | null;
  subcontract_executed: boolean | null;
  subcontract_signed_at: string | null;
  last_synced_at: string | null;
  source: "governance_os" | "stub";
};

export type CPTeamingPartnerRef = {
  id: string;
  name: string;
  uei: string | null;
  cage_code: string | null;
  capabilities: string[];
  naics_codes: string[];
  set_aside_certifications: string[];
  contact_name: string | null;
  contact_email: string | null;
  governance_doc_state: CPGovernanceDocState;
};

export type CPTeamingPartnersSection = {
  selected: CPTeamingPartnerRef[];
  library_size: number;
};

export type CPBidDecisionSection = {
  decision: "bid" | "no_bid" | "pending";
  pursuit_stage: string | null;
  decided_at: string | null;
  decider_user_id: string | null;
  decider_founder_slug: string | null;
  rationale: string | null;
  score: number | null;
  score_breakdown: Record<string, unknown> | null;
};

export type CPGovernanceReadinessSection = {
  accounting_system_dcaa_ready: boolean | null;
  accounting_system_provider: string | null;
  fcl_status: string | null;
  fcl_level: string | null;
  set_asides_held: string[];
  e_verify_enrolled: boolean | null;
  reps_certs_current: boolean | null;
  reps_certs_last_renewed_at: string | null;
  snapshot_at: string | null;
  source: "governance_os" | "stub";
};

export type CPQAEntry = {
  id: string;
  question: string;
  answer: string | null;
  asked_by_founder_slug: string | null;
  submitted_at: string | null;
  answered_at: string | null;
  starter_kind: string | null;
};

export type CPQAHistorySection = {
  entries: CPQAEntry[];
};

export type CPPackageCompleteness = {
  overall_pct: number;
  sections_complete: string[];
  sections_partial: string[];
  sections_missing: string[];
  gaps: string[];
};

/* ── Cyber Scope Parser ─────────────────────────────────────────── */

export type CyberScopeFeedItemOut = {
  id: string;
  opportunity_id: string | null;
  title: string | null;
  agency: string | null;
  solicitation_number: string | null;
  response_deadline: string | null;
  overall_cyber_likelihood: string;
  recommended_pursuit_model: string;
  score: number;
  ufgs_center_of_gravity: boolean;
  ufgs_tier_1_hit: boolean;
  top_ufgs_sections: string[];
  top_signals: Array<{
    term: string;
    normalized_term: string;
    weight: number;
    surrounding_text?: string;
  }>;
  scan_pass: string;
  attachments_pending: boolean;
  updated_at: string;
  opportunity_url: string | null;
};

export type CyberScopeFeedOut = {
  total: number;
  items: CyberScopeFeedItemOut[];
};

export type EmailDraftOut = {
  subject: string;
  body: string;
  generated_by: string;
  model: string | null;
};

export type SummaryOut = {
  summary: string;
  generated_by: string;
  model: string | null;
  generated_at: string;
};

export type IntelligenceBundleOut = {
  llm_summary: string | null;
  llm_summary_generated_by: string | null;
  llm_summary_at: string | null;
  clarification_email: EmailDraftOut | null;
  prime_outreach_email: EmailDraftOut | null;
  governance_handoff: Record<string, unknown> | null;
  pricing_handoff: Record<string, unknown> | null;
};

export type CyberScopeDownstreamOut = {
  clause_risk_log_id: string | null;
  bid_no_bid_review_id: string | null;
  proposal_outline_id: string | null;
  pursuit_id: string | null;
};

export type ClauseRiskLogOut = {
  id: string;
  opportunity_id: string;
  cyber_scope_analysis_id: string;
  title: string;
  status: string;
  entry_count: number;
  entries: Array<{
    id: string;
    sort_order: number;
    category: string;
    severity: string;
    reference: string;
    finding: string;
    evidence: string | null;
    mitigation: string | null;
  }>;
  created_at: string;
  updated_at: string;
};

export type BidNoBidReviewOut = {
  id: string;
  opportunity_id: string;
  cyber_scope_analysis_id: string;
  pursuit_id: string | null;
  recommended_decision: string;
  cyber_scope_summary: string;
  factors: Array<{ factor: string; weight: string; note: string }>;
  rationale_draft: string;
  pursuit_model: string | null;
  likelihood: string | null;
  score: number | null;
  created_at: string;
  updated_at: string;
};

export type ProposalOutlineOut = {
  id: string;
  opportunity_id: string;
  cyber_scope_analysis_id: string;
  title: string;
  sections: Array<{
    id: string;
    heading: string;
    bullets: string[];
  }>;
  status: string;
  created_at: string;
  updated_at: string;
};

export type CyberScopeAnalysisOut = {
  id: string;
  opportunity_id: string | null;
  source_type: string;
  scan_pass: string;
  parser_version: string;
  overall_cyber_likelihood: string;
  recommended_pursuit_model: string;
  score: number;
  ufgs_center_of_gravity: boolean;
  ufgs_tier_1_hit: boolean;
  detected_categories: Record<string, unknown>;
  top_signals: Array<Record<string, unknown>>;
  hidden_scope_indicators: Array<Record<string, unknown>>;
  missing_but_likely_requirements: string[];
  suggested_actions: Array<Record<string, unknown>>;
  evidence_snippets: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
  updated_at: string;
  downstream?: CyberScopeDownstreamOut | null;
};

export type CapturePackageOut = {
  schema_version: string;
  generated_at: string;
  tenant_id: string;
  tenant_slug: string;
  pursuit_id: string;

  opportunity: CPOpportunitySection;
  solicitation: CPSolicitationSection;
  compliance_matrix: CPComplianceMatrixSection;
  requirements_matrix: CPRequirementsMatrixSection;
  evaluation: CPEvaluationSection;
  cyber: CPCyberSection;
  capture_strategy: CPCaptureStrategySection;
  win_strategy: CPWinStrategySection;
  past_performance: CPPastPerformanceSection;
  key_personnel: CPKeyPersonnelSection;
  teaming_partners: CPTeamingPartnersSection;
  bid_decision: CPBidDecisionSection;
  governance_readiness: CPGovernanceReadinessSection;
  qa_history: CPQAHistorySection;
  completeness: CPPackageCompleteness;
};
