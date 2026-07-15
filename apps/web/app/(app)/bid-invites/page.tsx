import Link from "next/link";
import { BidInviteAction } from "@/components/bid-invite-actions";
import {
  apiFetch,
  type BidInviteListItem,
  type BidInviteStatus,
  type BidInvitesResponse
} from "@/lib/api";
import {
  pursueBidInvite,
  setBidInviteGroupStatus,
  setBidInviteStatus
} from "@/lib/bid-invites";
import {
  KIND_LABEL,
  KIND_TONE,
  dueMeta,
  groupBidInvites,
  type BidInviteGroup
} from "@/lib/bid-invite-view";
import { Badge, EmptyState, PageHeader, fmtDate } from "@/components/ui";

export const dynamic = "force-dynamic";

type Tab = "new" | "all" | "reviewed" | "archived";
type SP = Promise<{ tab?: string }>;

/**
 * Bid Invites — the inbound solicitation inbox. Gmail forwards every
 * BuildingConnected email to the Postmark webhook; here they arrive
 * grouped by project with the invite → reminder → due-date-change
 * thread collapsed into one card, ordered by how soon the bid is due.
 */
export default async function BidInvitesPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const tab: Tab = (["new", "all", "reviewed", "archived"] as const).includes(
    sp.tab as Tab
  )
    ? (sp.tab as Tab)
    : "new";

  const data = await apiFetch<BidInvitesResponse>("/bid-invites?limit=500");
  const visible =
    tab === "all" ? data.items : data.items.filter((i) => i.status === tab);
  const groups = groupBidInvites(visible);

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "new", label: "New", count: data.counts.new },
    { key: "all", label: "All", count: data.total },
    { key: "reviewed", label: "Reviewed", count: data.counts.reviewed },
    { key: "archived", label: "Archived", count: data.counts.archived }
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inbound"
        title="Bid Invites"
        subtitle="Solicitations from general contractors, forwarded from the BuildingConnected inbox and parsed automatically."
      />

      <nav className="flex flex-wrap items-center gap-1 border-b border-border pb-px text-sm">
        {tabs.map((t) => {
          const active = t.key === tab;
          return (
            <Link
              key={t.key}
              href={t.key === "new" ? "/bid-invites" : `/bid-invites?tab=${t.key}`}
              className={`inline-flex items-center gap-1.5 rounded-t-md border-b-2 px-3 py-2 font-medium transition-colors ${
                active
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
              <span className="rounded-sm bg-secondary px-1.5 text-[11px] tabular-nums text-muted-foreground">
                {t.count}
              </span>
            </Link>
          );
        })}
      </nav>

      {groups.length === 0 ? (
        <EmptyState
          title={
            tab === "new"
              ? "Inbox zero — no new bid invites."
              : "Nothing here."
          }
          body={
            data.total === 0
              ? "When a GC invites MacTech to bid on BuildingConnected, the email lands here automatically within seconds."
              : "Switch tabs to see the rest of the inbox."
          }
        />
      ) : (
        <div className="space-y-4">
          {groups.map((g) => (
            <ProjectCard key={g.key} group={g} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ group }: { group: BidInviteGroup }) {
  const due = dueMeta(group.bidDueOn);
  const newIds = group.items
    .filter((i) => i.status === "new")
    .map((i) => i.id);
  // Promote from the original invite when the thread has one — it
  // carries the fullest parse (package, location, due date); reminders
  // and replies can be sparse.
  const pursueFrom =
    group.items.find((i) => i.kind === "invite") ??
    group.items.find((i) => i.project_name) ??
    group.items[0];
  const meta = [
    group.gcCompany,
    group.leadName &&
      `${group.leadName}${group.leadPhone ? ` · ${group.leadPhone}` : ""}`,
    group.location
  ].filter(Boolean) as string[];

  return (
    <section className="rounded-md border border-border bg-card">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border p-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-foreground">
              {group.projectName}
            </h2>
            {due && <Badge tone={due.tone}>{due.label}</Badge>}
            {group.newCount > 0 && (
              <Badge tone="brand">
                {group.newCount} new
              </Badge>
            )}
          </div>
          {group.bidPackage && (
            <p className="mt-0.5 text-sm text-muted-foreground">
              Scope: {group.bidPackage}
            </p>
          )}
          {meta.length > 0 && (
            <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
              {meta.map((m, idx) => (
                <span key={m} className="inline-flex items-center gap-2">
                  {idx > 0 && <span aria-hidden>·</span>}
                  {m}
                </span>
              ))}
            </p>
          )}
          {!group.opportunityId && group.suggestedFounderName && (
            <p className="mt-1 text-xs text-muted-foreground">
              Routes to{" "}
              <span className="font-medium text-foreground">
                {group.suggestedFounderName}
              </span>{" "}
              — {group.suggestionReason}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {group.leadEmail && (
            <a
              href={`mailto:${group.leadEmail}`}
              className="text-xs font-medium text-primary hover:underline"
            >
              Email {group.leadName?.split(" ")[0] ?? "lead"}
            </a>
          )}
          {group.rfpUrl && (
            <a
              href={group.rfpUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center rounded-md border border-input bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent"
            >
              Open RFP ↗
            </a>
          )}
          {group.opportunityId ? (
            <Link
              href={`/opportunities/${group.opportunityId}`}
              className="inline-flex items-center rounded-md border border-success/40 bg-success/10 px-3 py-1.5 text-xs font-medium text-success transition-colors hover:bg-success/20"
            >
              In pipeline →
            </Link>
          ) : (
            <BidInviteAction
              action={pursueBidInvite.bind(null, pursueFrom.id)}
              label="Add to pipeline"
            />
          )}
          {newIds.length > 0 && (
            <BidInviteAction
              action={setBidInviteGroupStatus.bind(null, newIds, "reviewed")}
              label="Mark reviewed"
              variant="ghost"
            />
          )}
        </div>
      </header>

      <ul className="divide-y divide-border">
        {group.items.map((item) => (
          <InviteRow key={item.id} item={item} />
        ))}
      </ul>
    </section>
  );
}

function InviteRow({ item }: { item: BidInviteListItem }) {
  const kind = item.kind ?? "other";
  const attachmentCount = item.attachments?.length ?? 0;
  return (
    <li
      className={`flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 ${
        item.status === "archived" ? "opacity-60" : ""
      }`}
    >
      <Badge tone={KIND_TONE[kind]}>{KIND_LABEL[kind]}</Badge>
      <Link
        href={`/bid-invites/${item.id}`}
        className="min-w-0 flex-1 truncate text-sm text-foreground hover:text-primary"
        title={item.subject}
      >
        {item.headline ?? item.subject}
      </Link>
      {attachmentCount > 0 && (
        <span className="text-[11px] text-muted-foreground">
          {attachmentCount} attachment{attachmentCount === 1 ? "" : "s"}
        </span>
      )}
      <span className="text-[11px] tabular-nums text-muted-foreground">
        {fmtDate(item.received_at)}
      </span>
      {item.status === "new" ? (
        <BidInviteAction
          action={setBidInviteStatus.bind(null, item.id, "reviewed")}
          label="Review"
          variant="ghost"
        />
      ) : item.status === "reviewed" ? (
        <BidInviteAction
          action={setBidInviteStatus.bind(null, item.id, "archived")}
          label="Archive"
          variant="ghost"
        />
      ) : (
        <BidInviteAction
          action={setBidInviteStatus.bind(null, item.id, "new")}
          label="Reopen"
          variant="ghost"
        />
      )}
    </li>
  );
}
