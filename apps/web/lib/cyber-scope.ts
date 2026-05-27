"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type {
  BidNoBidReviewOut,
  ClauseRiskLogOut,
  CyberScopeAnalysisOut,
  CyberScopeFeedOut,
  EmailDraftOut,
  IntelligenceBundleOut,
  ProposalOutlineOut,
  SummaryOut,
} from "@/lib/api";

export async function fetchCyberScopeFeed(params?: {
  likelihood?: string;
  center_of_gravity?: boolean;
  ufgs_tier_1?: boolean;
  min_score?: number;
}): Promise<CyberScopeFeedOut> {
  const q = new URLSearchParams();
  if (params?.likelihood) q.set("likelihood", params.likelihood);
  if (params?.center_of_gravity) q.set("center_of_gravity", "true");
  if (params?.ufgs_tier_1) q.set("ufgs_tier_1", "true");
  if (params?.min_score != null) q.set("min_score", String(params.min_score));
  const qs = q.toString();
  return apiFetch<CyberScopeFeedOut>(
    `/tools/cyber-scope/feed${qs ? `?${qs}` : ""}`
  );
}

export async function fetchCyberScopeAnalysis(
  id: string
): Promise<CyberScopeAnalysisOut> {
  return apiFetch<CyberScopeAnalysisOut>(`/tools/cyber-scope/analyses/${id}`);
}

export async function rescanOpportunityCyberScope(
  opportunityId: string
): Promise<void> {
  const result = await apiFetch<CyberScopeAnalysisOut>(
    `/tools/cyber-scope/opportunities/${opportunityId}/rescan`,
    { method: "POST", body: JSON.stringify({}) }
  );
  revalidatePath("/tools/cyber-scope-parser");
  revalidatePath(`/opportunities/${opportunityId}`);
  redirect(`/tools/cyber-scope-parser/${result.id}`);
}

export async function analyzePastedCyberScope(formData: FormData): Promise<void> {
  const text = String(formData.get("text") ?? "").trim();
  if (text.length < 10) {
    throw new Error("Paste at least 10 characters of solicitation text.");
  }
  const result = await apiFetch<CyberScopeAnalysisOut>("/tools/cyber-scope/analyze", {
    method: "POST",
    body: JSON.stringify({
      text,
      title: formData.get("title") || undefined,
      agency: formData.get("agency") || undefined,
      solicitation_number: formData.get("solicitation_number") || undefined,
      opportunity_id: formData.get("opportunity_id") || undefined,
    }),
  });
  revalidatePath("/tools/cyber-scope-parser");
  redirect(`/tools/cyber-scope-parser/${result.id}`);
}

export async function createClauseRiskLogFromAnalysis(
  analysisId: string
): Promise<void> {
  const log = await apiFetch<ClauseRiskLogOut>(
    `/tools/cyber-scope/analyses/${analysisId}/clause-risk-log`,
    { method: "POST", body: JSON.stringify({}) }
  );
  revalidatePath("/tools/cyber-scope-parser");
  revalidatePath(`/tools/cyber-scope-parser/${analysisId}`);
  redirect(`/tools/cyber-scope-parser/clause-risk/${log.id}`);
}

export async function createBidNoBidReviewFromAnalysis(
  analysisId: string
): Promise<void> {
  const review = await apiFetch<BidNoBidReviewOut>(
    `/tools/cyber-scope/analyses/${analysisId}/bid-no-bid-review`,
    { method: "POST", body: JSON.stringify({}) }
  );
  revalidatePath("/tools/cyber-scope-parser");
  revalidatePath(`/tools/cyber-scope-parser/${analysisId}`);
  redirect(`/tools/cyber-scope-parser/bid-review/${review.id}`);
}

export async function createProposalOutlineFromAnalysis(
  analysisId: string
): Promise<void> {
  const outline = await apiFetch<ProposalOutlineOut>(
    `/tools/cyber-scope/analyses/${analysisId}/proposal-outline`,
    { method: "POST", body: JSON.stringify({}) }
  );
  revalidatePath("/tools/cyber-scope-parser");
  revalidatePath(`/tools/cyber-scope-parser/${analysisId}`);
  redirect(`/tools/cyber-scope-parser/outline/${outline.id}`);
}

export async function addCyberScopeToPipeline(analysisId: string): Promise<void> {
  const result = await apiFetch<{
    pursuit_id: string;
    created: boolean;
    opportunity_url: string;
  }>(`/tools/cyber-scope/analyses/${analysisId}/add-to-pipeline`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  revalidatePath("/pipeline");
  revalidatePath("/tools/cyber-scope-parser");
  revalidatePath(`/tools/cyber-scope-parser/${analysisId}`);
  redirect(`/pursuits/${result.pursuit_id}`);
}

export async function fetchClauseRiskLog(id: string): Promise<ClauseRiskLogOut> {
  return apiFetch<ClauseRiskLogOut>(`/tools/cyber-scope/clause-risk-logs/${id}`);
}

export async function fetchBidNoBidReview(id: string): Promise<BidNoBidReviewOut> {
  return apiFetch<BidNoBidReviewOut>(`/tools/cyber-scope/bid-no-bid-reviews/${id}`);
}

export async function fetchProposalOutline(id: string): Promise<ProposalOutlineOut> {
  return apiFetch<ProposalOutlineOut>(`/tools/cyber-scope/proposal-outlines/${id}`);
}

export async function fetchCyberScopeIntelligence(
  analysisId: string
): Promise<IntelligenceBundleOut> {
  return apiFetch<IntelligenceBundleOut>(
    `/tools/cyber-scope/analyses/${analysisId}/intelligence`
  );
}

export async function generateCyberScopeSummary(analysisId: string): Promise<void> {
  await apiFetch<SummaryOut>(
    `/tools/cyber-scope/analyses/${analysisId}/summarize`,
    { method: "POST", body: JSON.stringify({}) }
  );
  revalidatePath(`/tools/cyber-scope-parser/${analysisId}`);
}

export async function generateClarificationEmail(analysisId: string): Promise<void> {
  await apiFetch<EmailDraftOut>(
    `/tools/cyber-scope/analyses/${analysisId}/clarification-email`,
    { method: "POST", body: JSON.stringify({}) }
  );
  revalidatePath(`/tools/cyber-scope-parser/${analysisId}`);
}

export async function generatePrimeOutreachEmail(analysisId: string): Promise<void> {
  await apiFetch<EmailDraftOut>(
    `/tools/cyber-scope/analyses/${analysisId}/prime-outreach-email`,
    { method: "POST", body: JSON.stringify({}) }
  );
  revalidatePath(`/tools/cyber-scope-parser/${analysisId}`);
}

export type CyberScopeSamSearchStatusOut = {
  state_key: string;
  last_run_at: string | null;
  last_success_at: string | null;
  last_status: string | null;
  last_error: string | null;
};

export type CyberScopeSamSearchRunOut = {
  status: string;
  jobs_run: number;
  total_matched: number;
  total_upserts: number;
  errors: number;
};

export async function fetchCyberScopeSamSearchStatus(): Promise<
  CyberScopeSamSearchStatusOut[]
> {
  return apiFetch<CyberScopeSamSearchStatusOut[]>(
    "/tools/cyber-scope/sam-search/status"
  );
}

export async function runCyberScopeSamSearch(): Promise<CyberScopeSamSearchRunOut> {
  const result = await apiFetch<CyberScopeSamSearchRunOut>(
    "/tools/cyber-scope/sam-search/run",
    { method: "POST", body: JSON.stringify({}) }
  );
  revalidatePath("/tools/cyber-scope-parser");
  return result;
}
