import Link from "next/link";
import { notFound } from "next/navigation";
import { apiFetch, type DraftOut, type DraftStatus } from "@/lib/api";
import {
  deleteDraft,
  setDraftStatus,
  updateDraftContent
} from "@/lib/drafts";
import {
  BackLink,
  Badge,
  Button,
  LinkButton,
  NoticeTypeBadge,
  PageHeader,
  fmtDate
} from "@/components/ui";
import { TermPopover } from "@/components/term-popover";
import { StreamingRegeneratePanel } from "@/components/draft-streaming";

export const dynamic = "force-dynamic";

const STATUS_LABEL: Record<DraftStatus, string> = {
  draft: "Draft",
  reviewed: "Reviewed",
  submitted: "Submitted",
  archived: "Archived"
};

const STATUS_TONE: Record<DraftStatus, "neutral" | "blue" | "green" | "amber"> = {
  draft: "neutral",
  reviewed: "blue",
  submitted: "green",
  archived: "amber"
};

const STATUS_FLOW: Record<DraftStatus, DraftStatus[]> = {
  draft: ["reviewed", "archived"],
  reviewed: ["submitted", "draft"],
  submitted: ["archived"],
  archived: ["draft"]
};

export default async function DraftDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let draft: DraftOut;
  try {
    draft = await apiFetch<DraftOut>(`/drafts/${id}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  const updateAction = updateDraftContent.bind(null, draft.id);
  const tokensInOut = `${draft.input_tokens?.toLocaleString() ?? "?"} in · ${draft.output_tokens?.toLocaleString() ?? "?"} out`;
  const allowedStatuses = STATUS_FLOW[draft.status] ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <BackLink href="/drafts">All drafts</BackLink>
        <Link
          href={`/opportunities/${draft.opportunity.id}`}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Source opportunity →
        </Link>
      </div>

      <PageHeader
        eyebrow={`v${draft.version}`}
        title={draft.title}
        subtitle={
          <span className="inline-flex flex-wrap items-center gap-2">
            <TermPopover kind="draft_status" value={draft.status}>
              <Badge tone={STATUS_TONE[draft.status]}>
                {STATUS_LABEL[draft.status]}
              </Badge>
            </TermPopover>
            <TermPopover kind="draft_type" value={draft.draft_type}>
              <Badge tone="violet">
                {draft.draft_type.replaceAll("_", " ")}
              </Badge>
            </TermPopover>
            {draft.opportunity.notice_type && (
              <NoticeTypeBadge type={draft.opportunity.notice_type} />
            )}
            <span className="text-muted-foreground">·</span>
            <span>{draft.opportunity.title}</span>
          </span>
        }
        trailing={
          <div className="flex flex-wrap items-center gap-2">
            <LinkButton
              href={`/drafts/${draft.id}/export.docx`}
              variant="primary"
              size="sm"
              title="Download this draft as a Microsoft Word document"
            >
              ⬇ Export DOCX
            </LinkButton>
            {allowedStatuses.map((s) => (
              <form key={s} action={setDraftStatus}>
                <input type="hidden" name="id" value={draft.id} />
                <input type="hidden" name="status" value={s} />
                <Button
                  type="submit"
                  variant={s === "submitted" ? "success" : "secondary"}
                  size="sm"
                >
                  Mark {STATUS_LABEL[s].toLowerCase()}
                </Button>
              </form>
            ))}
            <form action={deleteDraft}>
              <input type="hidden" name="id" value={draft.id} />
              <input
                type="hidden"
                name="opportunity_id"
                value={draft.opportunity.id}
              />
              <input type="hidden" name="redirect_to" value="/drafts" />
              <Button type="submit" variant="danger" size="sm" title="Delete this draft permanently">
                Delete
              </Button>
            </form>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Editor — full width on small, 2/3 on large */}
        <section className="lg:col-span-2">
          <form action={updateAction} className="space-y-3">
            <label className="block">
              <span className="block text-[11px] uppercase tracking-wider text-muted-foreground">
                Title
              </span>
              <input
                name="title"
                defaultValue={draft.title}
                className="mt-1 w-full rounded-md border border-border bg-card px-3 py-2 text-sm shadow-sm focus:border-foreground/40 focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="block text-[11px] uppercase tracking-wider text-muted-foreground">
                Draft content (markdown)
              </span>
              <textarea
                name="content"
                defaultValue={draft.content}
                rows={36}
                className="mt-1 w-full rounded-md border border-border bg-card px-3 py-3 font-mono text-[13px] leading-relaxed shadow-sm focus:border-foreground/40 focus:outline-none"
              />
            </label>
            <div className="flex items-center justify-end gap-2">
              <LinkButton href="/drafts" variant="secondary">
                Cancel
              </LinkButton>
              <Button type="submit" variant="primary">
                Save changes
              </Button>
            </div>
          </form>
        </section>

        {/* Side panel — generation metadata + regenerate form */}
        <aside className="space-y-4">
          <div className="rounded-md border border-border bg-card p-4">
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Generation metadata
            </p>
            <dl className="mt-3 space-y-2 text-xs">
              <Row label="Model">{draft.model ?? "—"}</Row>
              <Row label="Tokens">{tokensInOut}</Row>
              <Row label="Created">{fmtDate(draft.created_at)}</Row>
              {draft.parent_draft_id && (
                <Row label="Parent">
                  <Link
                    href={`/drafts/${draft.parent_draft_id}`}
                    className="text-primary hover:underline"
                  >
                    v{draft.version - 1}
                  </Link>
                </Row>
              )}
              {draft.created_by && (
                <Row label="Author">
                  {draft.created_by.full_name}{" "}
                  <span className="text-muted-foreground">
                    @{draft.created_by.slug}
                  </span>
                </Row>
              )}
              {draft.citations &&
                typeof draft.citations === "object" && (
                  <>
                    <Row label="Capabilities cited">
                      {String((draft.citations as Record<string, unknown>)["capability_count"] ?? 0)}
                    </Row>
                    <Row label="Past performance">
                      {String((draft.citations as Record<string, unknown>)["past_performance_count"] ?? 0)}
                    </Row>
                    <Row label="Teaming partners">
                      {String((draft.citations as Record<string, unknown>)["teaming_partner_count"] ?? 0)}
                    </Row>
                  </>
                )}
            </dl>
          </div>

          <div className="rounded-md border border-border bg-card p-4">
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Regenerate
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              Run the drafter again with the same context. Optionally add custom
              instructions — the new version will be a child of this one.
            </p>
            <div className="mt-3">
              <StreamingRegeneratePanel
                draftId={draft.id}
                initialInstructions={draft.custom_instructions}
                nextVersion={draft.version + 1}
              />
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}
