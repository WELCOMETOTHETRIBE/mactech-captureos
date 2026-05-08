import Link from "next/link";
import { apiFetch, type DraftListResponse, type DraftStatus } from "@/lib/api";
import {
  Badge,
  EmptyState,
  LinkButton,
  NoticeTypeBadge,
  PageHeader,
  fmtDate
} from "@/components/ui";
import { TermPopover } from "@/components/term-popover";

export const dynamic = "force-dynamic";

const DRAFT_TYPE_LABEL: Record<string, string> = {
  sources_sought: "Sources Sought",
  rfp_response: "RFP response",
  compliance_matrix: "Compliance matrix",
  white_paper: "White paper"
};

const STATUS_TONE: Record<DraftStatus, "neutral" | "blue" | "green" | "amber"> = {
  draft: "neutral",
  reviewed: "blue",
  submitted: "green",
  archived: "amber"
};

export default async function DraftsListPage() {
  const data = await apiFetch<DraftListResponse>("/drafts");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Proposal drafts"
        title="Drafts"
        subtitle={
          <>
            <TermPopover kind="draft_type" value="sources_sought">
              Sources Sought
            </TermPopover>{" "}
            responses,{" "}
            <TermPopover kind="draft_type" value="rfp_response">
              RFP
            </TermPopover>{" "}
            drafts, and{" "}
            <TermPopover kind="draft_type" value="compliance_matrix">
              compliance matrices
            </TermPopover>{" "}
            the AI drafter has produced. Each draft is editable, regeneratable,
            and trackable through review → submission.
          </>
        }
      />

      {data.items.length === 0 ? (
        <EmptyState
          title="No drafts yet."
          body="Open any Sources Sought opportunity and click 'Draft response' — Claude generates a starting point using your capability statements, past performance, and active teaming partners."
          action={
            <LinkButton
              href="/opportunities?notice_type=Sources+Sought"
              variant="primary"
            >
              Find Sources Sought opps
            </LinkButton>
          }
        />
      ) : (
        <ul className="space-y-3">
          {data.items.map((d) => (
            <li key={d.id}>
              <Link
                href={`/drafts/${d.id}`}
                className="block rounded-md border border-border bg-card p-4 transition-colors hover:border-foreground/30"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <TermPopover kind="draft_status" value={d.status}>
                      <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>
                        {d.status}
                      </Badge>
                    </TermPopover>
                    <TermPopover kind="draft_type" value={d.draft_type}>
                      <Badge tone="violet">
                        {DRAFT_TYPE_LABEL[d.draft_type] ?? d.draft_type}
                      </Badge>
                    </TermPopover>
                    {d.version > 1 && (
                      <span className="text-[11px] text-muted-foreground tabular-nums">
                        v{d.version}
                      </span>
                    )}
                    {d.opportunity.notice_type && (
                      <NoticeTypeBadge type={d.opportunity.notice_type} />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {fmtDate(d.created_at)}
                  </p>
                </div>
                <h3 className="mt-2 text-sm font-semibold leading-snug text-foreground">
                  {d.title}
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Opp: {d.opportunity.title}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-x-3 text-[11px] text-muted-foreground">
                  {d.model && <span>model {d.model}</span>}
                  {d.output_tokens != null && (
                    <span>{d.output_tokens.toLocaleString()} tokens</span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
