import type { PursuitStage } from "@/lib/api";
import { PURSUIT_STAGES_ORDER } from "@/lib/api";

/**
 * Pursuit stage tone + label vocabulary.
 *
 * Single source of truth for how the pipeline lifecycle paints across
 * the suite — pipeline kanban, opportunity detail pursuit panel, pursuit
 * detail meta strip. Before this lived as three slightly-different copies
 * in three pages; the user saw the same lifecycle painted differently
 * depending on which page they entered through.
 *
 * The values flow through `<Badge tone>` (which resolves to semantic
 * tokens) so a future re-skin of `--success`, `--warning`, etc. updates
 * every stage chip in the app.
 *
 * Note: kept in a separate module from `lib/pursuits.ts` because that
 * file is `"use server"` only and can't export plain constants.
 */
export const STAGE_TONE: Record<
  PursuitStage,
  "neutral" | "blue" | "amber" | "violet" | "brand" | "green" | "red"
> = {
  lead: "neutral",
  qualify: "blue",
  pursue: "amber",
  propose: "violet",
  submit: "brand",
  won: "green",
  lost: "red",
};

export const STAGE_LABEL: Record<PursuitStage, string> = {
  lead: "Lead",
  qualify: "Qualify",
  pursue: "Pursue",
  propose: "Propose",
  submit: "Submit",
  won: "Won",
  lost: "Lost",
};

/** Re-export for callers who want a single import. */
export const STAGE_ORDER = PURSUIT_STAGES_ORDER;

/** Per-stage plain-English explanation. Used by the `<Term kind="pursuit_stage">`
 *  popover when the explain backend hasn't generated a row yet. */
export const STAGE_HELP: Record<PursuitStage, string> = {
  lead:
    "Earliest signal. We've noticed the opportunity but haven't decided if it's worth pursuing. No qualification work has happened yet.",
  qualify:
    "We're confirming fit. Reading the SAM description, scanning the brief, checking incumbent intel and capability matches. Bid/no-bid not decided.",
  pursue:
    "Bid decision is yes. We're shaping the win — talking to the customer, refining win themes, lining up teaming partners or key personnel.",
  propose:
    "Drafting the proposal. Compliance matrix is being built; volumes are coming together. The clock is the response deadline.",
  submit:
    "Proposal is in the agency's hands. Awaiting evaluation. Sometimes we'll respond to clarification questions in this stage.",
  won:
    "We won the award. Past this point the work moves into ProposalOS / delivery; the pursuit stays here for win-loss analysis.",
  lost:
    "We didn't win. Could be losing on price, technical, or pre-award protest — capture the lesson in the pursuit notes for next time.",
};
