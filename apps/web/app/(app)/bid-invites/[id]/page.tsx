import Link from "next/link";
import { notFound } from "next/navigation";
import { BidInviteAction } from "@/components/bid-invite-actions";
import { apiFetch, type BidInviteDetail } from "@/lib/api";
import { pursueBidInvite, setBidInviteStatus } from "@/lib/bid-invites";
import { KIND_LABEL, KIND_TONE, dueMeta } from "@/lib/bid-invite-view";
import { BackLink, Badge, PageHeader, fmtDate } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function BidInviteDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let invite: BidInviteDetail;
  try {
    invite = await apiFetch<BidInviteDetail>(`/bid-invites/${id}`);
  } catch {
    notFound();
  }

  const due = dueMeta(invite.bid_due_on);
  const kind = invite.kind ?? "other";
  const attachments = invite.attachments ?? [];

  return (
    <div className="space-y-6">
      <BackLink href="/bid-invites">Bid invites</BackLink>

      <PageHeader
        display
        eyebrow={invite.gc_company ?? "Bid invite"}
        title={invite.project_name ?? invite.subject}
        subtitle={
          <span className="inline-flex flex-wrap items-center gap-2">
            <Badge tone={KIND_TONE[kind]}>{KIND_LABEL[kind]}</Badge>
            {due && <Badge tone={due.tone}>{due.label}</Badge>}
            {invite.bid_package && (
              <span className="text-sm text-muted-foreground">
                Scope: {invite.bid_package}
              </span>
            )}
            {!invite.opportunity_id && invite.suggested_founder_name && (
              <span className="text-sm text-muted-foreground">
                · Routes to{" "}
                <span className="font-medium text-foreground">
                  {invite.suggested_founder_name}
                </span>{" "}
                — {invite.suggestion_reason}
              </span>
            )}
          </span>
        }
        trailing={
          <div className="flex items-center gap-2">
            {invite.opportunity_id ? (
              <Link
                href={`/opportunities/${invite.opportunity_id}`}
                className="inline-flex items-center rounded-md border border-success/40 bg-success/10 px-3.5 py-2 text-sm font-medium text-success transition-colors hover:bg-success/20"
              >
                In pipeline →
              </Link>
            ) : (
              <BidInviteAction
                action={pursueBidInvite.bind(null, invite.id)}
                label="Add to pipeline"
              />
            )}
            {invite.rfp_url && (
              <a
                href={invite.rfp_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-md border border-primary bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Open in BuildingConnected ↗
              </a>
            )}
            {invite.status === "new" ? (
              <BidInviteAction
                action={setBidInviteStatus.bind(null, invite.id, "reviewed")}
                label="Mark reviewed"
              />
            ) : invite.status === "reviewed" ? (
              <BidInviteAction
                action={setBidInviteStatus.bind(null, invite.id, "archived")}
                label="Archive"
              />
            ) : (
              <BidInviteAction
                action={setBidInviteStatus.bind(null, invite.id, "new")}
                label="Reopen"
              />
            )}
          </div>
        }
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="General contractor" value={invite.gc_company} />
        <Fact
          label="Lead"
          value={
            invite.lead_name && (
              <span className="flex flex-col gap-0.5">
                <span>{invite.lead_name}</span>
                {invite.lead_email && (
                  <a
                    href={`mailto:${invite.lead_email}`}
                    className="text-xs text-primary hover:underline"
                  >
                    {invite.lead_email}
                  </a>
                )}
                {invite.lead_phone && (
                  <a
                    href={`tel:${invite.lead_phone.replace(/[^+\d]/g, "")}`}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    {invite.lead_phone}
                  </a>
                )}
              </span>
            )
          }
        />
        <Fact label="Location" value={invite.location} />
        <Fact
          label="Bid due"
          value={
            invite.bid_due_on && (
              <span className="inline-flex items-center gap-2">
                {fmtDate(invite.bid_due_on)}
                {due && due.tone !== "neutral" && (
                  <Badge tone={due.tone}>{due.label}</Badge>
                )}
              </span>
            )
          }
        />
      </section>

      {attachments.length > 0 && (
        <section className="rounded-md border border-border bg-card p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Attachments ({attachments.length})
          </p>
          <ul className="mt-2 space-y-1">
            {attachments.map((a, idx) => (
              <li key={`${a.name}-${idx}`} className="text-sm text-foreground">
                {a.name ?? "unnamed"}
                <span className="ml-2 text-xs text-muted-foreground">
                  {a.content_type ?? ""}
                  {a.size ? ` · ${fmtBytes(a.size)}` : ""}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted-foreground">
            Files live in BuildingConnected — open the RFP above to download
            them.
          </p>
        </section>
      )}

      <section className="rounded-md border border-border bg-card">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Original email
          </p>
          {/* arrived_at, not received_at — the latter is ingest time, so
              backfilled mail would claim it arrived on import day. */}
          <p
            className="text-xs text-muted-foreground"
            title={new Date(invite.arrived_at).toLocaleString()}
          >
            {invite.from_name ?? invite.from_email ?? "unknown sender"} ·
            received {fmtDate(invite.arrived_at)}
          </p>
        </header>
        {invite.html_body ? (
          // Sandboxed with no permissions: BuildingConnected HTML renders,
          // but scripts, forms, and top-navigation are all inert.
          <iframe
            title="Original email"
            sandbox=""
            srcDoc={invite.html_body}
            className="h-[70vh] w-full rounded-b-md bg-white"
          />
        ) : (
          <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap p-4 text-sm text-foreground">
            {invite.text_body ?? "No body captured."}
          </pre>
        )}
      </section>
    </div>
  );
}

function Fact({
  label,
  value
}: {
  label: string;
  value: React.ReactNode | null | undefined;
}) {
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="mt-1 text-sm text-foreground">
        {value || <span className="text-muted-foreground">—</span>}
      </div>
    </div>
  );
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
