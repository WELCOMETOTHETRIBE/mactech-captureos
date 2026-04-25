import Link from "next/link";
import { apiFetch, type DraftListResponse, type DraftStatus } from "@/lib/api";
import {
  Badge,
  EmptyState,
  NoticeTypeBadge,
  PageHeader,
  fmtDate
} from "@/components/ui";

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
        subtitle="Sources Sought responses, RFP drafts, and compliance matrices the AI drafter has produced. Each draft is editable, regeneratable, and trackable through review → submission."
      />

      {data.items.length === 0 ? (
        <EmptyState
          title="No drafts yet."
          body="Open any Sources Sought opportunity and click 'Draft response' — Claude generates a starting point using your capability statements, past performance, and active teaming partners."
          action={
            <Link
              href="/opportunities?notice_type=Sources+Sought"
              className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-800"
            >
              Find Sources Sought opps
            </Link>
          }
        />
      ) : (
        <ul className="space-y-3">
          {data.items.map((d) => (
            <li key={d.id}>
              <Link
                href={`/drafts/${d.id}`}
                className="block rounded-md border border-neutral-200 bg-white p-4 transition-colors hover:border-neutral-400"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>
                      {d.status}
                    </Badge>
                    <Badge tone="violet">
                      {DRAFT_TYPE_LABEL[d.draft_type] ?? d.draft_type}
                    </Badge>
                    {d.version > 1 && (
                      <span className="text-[11px] text-neutral-500 tabular-nums">
                        v{d.version}
                      </span>
                    )}
                    {d.opportunity.notice_type && (
                      <NoticeTypeBadge type={d.opportunity.notice_type} />
                    )}
                  </div>
                  <p className="text-xs text-neutral-500">
                    {fmtDate(d.created_at)}
                  </p>
                </div>
                <h3 className="mt-2 text-sm font-semibold leading-snug text-neutral-900">
                  {d.title}
                </h3>
                <p className="mt-1 text-xs text-neutral-500">
                  Opp: {d.opportunity.title}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-x-3 text-[11px] text-neutral-500">
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
