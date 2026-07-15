import type { BidInviteListItem } from "@/lib/api";

/**
 * View-model helpers for bid-invite surfaces (triage page + dashboard
 * rail). Pure functions — no fetching, no server actions — so both
 * server components can share one grouping/urgency contract.
 *
 * Grouping: BuildingConnected sends several emails per solicitation
 * (invite → reminders → due-date changes → addenda). The stable RFP id
 * only appears on message-type mail, so the group key is the
 * normalized project name — "Kings Bay Project" and "Kings Bay" both
 * land in one card.
 */

export type BidInviteGroup = {
  key: string;
  projectName: string;
  bidPackage: string | null;
  gcCompany: string | null;
  leadName: string | null;
  leadEmail: string | null;
  leadPhone: string | null;
  location: string | null;
  /** Effective deadline: from the most recent email that states one,
   * so a "Due Date Extended" supersedes the original invite. */
  bidDueOn: string | null;
  rfpUrl: string | null;
  /** Set once the project has been promoted into the pipeline. */
  opportunityId: string | null;
  suggestedFounderName: string | null;
  suggestionReason: string | null;
  /** True arrival of the newest email in the thread. */
  latestArrived: string;
  /** Untriaged emails in the thread — the durable backlog. */
  newCount: number;
  /** Emails that arrived since you last acknowledged the inbox. Drives
   * the unseen band and highlight; a subset of newCount. */
  unseenCount: number;
  /** Newest first. */
  items: BidInviteListItem[];
};

function normalizeProjectKey(invite: BidInviteListItem): string {
  const raw = invite.project_name ?? invite.subject;
  return (
    raw
      .toLowerCase()
      .replace(/\bproject\b/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim() || invite.id
  );
}

export function groupBidInvites(items: BidInviteListItem[]): BidInviteGroup[] {
  const byKey = new Map<string, BidInviteListItem[]>();
  for (const item of items) {
    const key = normalizeProjectKey(item);
    const bucket = byKey.get(key);
    if (bucket) bucket.push(item);
    else byKey.set(key, [item]);
  }

  const groups: BidInviteGroup[] = [];
  for (const [key, bucket] of byKey) {
    bucket.sort((a, b) => b.arrived_at.localeCompare(a.arrived_at));
    const first = <T,>(pick: (i: BidInviteListItem) => T | null): T | null => {
      for (const i of bucket) {
        const v = pick(i);
        if (v) return v;
      }
      return null;
    };
    groups.push({
      key,
      projectName: first((i) => i.project_name) ?? bucket[0].subject,
      bidPackage: first((i) => i.bid_package),
      gcCompany: first((i) => i.gc_company),
      leadName: first((i) => i.lead_name),
      leadEmail: first((i) => i.lead_email),
      leadPhone: first((i) => i.lead_phone),
      location: first((i) => i.location),
      bidDueOn: first((i) => i.bid_due_on),
      rfpUrl: first((i) => i.rfp_url),
      opportunityId: first((i) => i.opportunity_id),
      suggestedFounderName: first((i) => i.suggested_founder_name),
      suggestionReason: first((i) => i.suggestion_reason),
      latestArrived: bucket[0].arrived_at,
      newCount: bucket.filter((i) => i.status === "new").length,
      unseenCount: bucket.filter((i) => i.unseen).length,
      items: bucket
    });
  }

  // Order: anything that arrived since you last looked pins to the top,
  // newest first — mail you haven't seen must never hide mid-list behind
  // a distant deadline. Everything below keeps the deadline triage
  // order: live deadlines soonest-first, then undated work (newest
  // first), then already-closed solicitations at the bottom.
  const today = todayISO();
  const rank = (g: BidInviteGroup) => {
    if (g.unseenCount > 0) return 0;
    if (g.bidDueOn === null) return 2;
    return g.bidDueOn >= today ? 1 : 3;
  };
  groups.sort((a, b) => {
    const ra = rank(a);
    const r = ra - rank(b);
    if (r !== 0) return r;
    if (ra === 0) return b.latestArrived.localeCompare(a.latestArrived);
    if (ra === 1) return a.bidDueOn!.localeCompare(b.bidDueOn!);
    if (ra === 3) return b.bidDueOn!.localeCompare(a.bidDueOn!);
    return b.latestArrived.localeCompare(a.latestArrived);
  });
  return groups;
}

/** Index of the first group below the unseen band, i.e. the band's size.
 * The page uses this to draw a divider between "new since you looked"
 * and the standing triage list. */
export function unseenBandSize(groups: BidInviteGroup[]): number {
  return groups.filter((g) => g.unseenCount > 0).length;
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export type DueMeta = {
  tone: "neutral" | "amber" | "red";
  label: string;
  daysLeft: number | null;
};

/** Urgency chip contract: red ≤3 days, amber ≤7, neutral otherwise;
 * past deadlines read as "closed" so dead invites stop shouting. */
export function dueMeta(bidDueOn: string | null): DueMeta | null {
  if (!bidDueOn) return null;
  const msPerDay = 86_400_000;
  const days = Math.round(
    (new Date(`${bidDueOn}T00:00:00`).getTime() -
      new Date(`${todayISO()}T00:00:00`).getTime()) /
      msPerDay
  );
  const pretty = new Date(`${bidDueOn}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric"
  });
  if (days < 0) return { tone: "neutral", label: `closed ${pretty}`, daysLeft: days };
  if (days === 0) return { tone: "red", label: "due today", daysLeft: days };
  if (days === 1) return { tone: "red", label: "due tomorrow", daysLeft: days };
  if (days <= 3) return { tone: "red", label: `due in ${days}d`, daysLeft: days };
  if (days <= 7) return { tone: "amber", label: `due in ${days}d`, daysLeft: days };
  return { tone: "neutral", label: `due ${pretty}`, daysLeft: days };
}

/**
 * Force every link in a rendered email to open in a new tab.
 *
 * BuildingConnected links its RFP with a bare `<a href>` and no target,
 * which inside an iframe means "navigate this iframe": the reader loses
 * the email and lands on a JS app that can't boot, since the frame's
 * sandbox revokes scripts. One `<base target="_blank">` retargets the
 * whole document without rewriting links one by one.
 *
 * Placement matters. The tag has to land in <head>, and it must never be
 * prepended ahead of a doctype — that flips the document into quirks mode
 * and reflows the table layout every HTML email is built on. So: insert
 * after <head> when there is one (59 of 60 stored emails), synthesize a
 * head under <html> if needed, insert after a lone doctype, and only
 * prepend for a bare fragment, where there's no doctype to displace.
 *
 * Browsers imply rel=noopener for target=_blank, and the frame has no
 * scripts anyway, so the opened tab can't reach back through opener.
 */
export function withBlankLinkTarget(html: string): string {
  const base = '<base target="_blank">';
  const head = html.match(/<head[^>]*>/i);
  if (head) return html.replace(head[0], `${head[0]}${base}`);
  const htmlTag = html.match(/<html[^>]*>/i);
  if (htmlTag) return html.replace(htmlTag[0], `${htmlTag[0]}<head>${base}</head>`);
  const doctype = html.match(/^\s*<!doctype[^>]*>/i);
  if (doctype) return html.replace(doctype[0], `${doctype[0]}${base}`);
  return base + html;
}

export const KIND_LABEL: Record<string, string> = {
  invite: "invite",
  reminder: "reminder",
  due_date_change: "due date change",
  addendum: "addendum",
  message: "message",
  reply: "reply",
  other: "email"
};

export const KIND_TONE: Record<
  string,
  "neutral" | "blue" | "green" | "amber" | "red" | "violet" | "brand"
> = {
  invite: "brand",
  reminder: "amber",
  due_date_change: "red",
  addendum: "violet",
  message: "blue",
  reply: "neutral",
  other: "neutral"
};
