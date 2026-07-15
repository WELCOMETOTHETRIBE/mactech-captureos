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
  latestReceived: string;
  newCount: number;
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
    bucket.sort((a, b) => b.received_at.localeCompare(a.received_at));
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
      latestReceived: bucket[0].received_at,
      newCount: bucket.filter((i) => i.status === "new").length,
      items: bucket
    });
  }

  // Triage order: live deadlines soonest-first, then undated work
  // (newest first), then already-closed solicitations at the bottom.
  const today = todayISO();
  const rank = (g: BidInviteGroup) =>
    g.bidDueOn === null ? 1 : g.bidDueOn >= today ? 0 : 2;
  groups.sort((a, b) => {
    const r = rank(a) - rank(b);
    if (r !== 0) return r;
    if (rank(a) === 0) return a.bidDueOn!.localeCompare(b.bidDueOn!);
    if (rank(a) === 2) return b.bidDueOn!.localeCompare(a.bidDueOn!);
    return b.latestReceived.localeCompare(a.latestReceived);
  });
  return groups;
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
