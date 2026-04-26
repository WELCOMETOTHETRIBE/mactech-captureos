import Link from "next/link";
import { notFound } from "next/navigation";
import { apiFetch, type DraftOut, type DraftStatus } from "@/lib/api";
import {
  deleteDraft,
  setDraftStatus,
  updateDraftContent
} from "@/lib/drafts";
import {
  Badge,
  NoticeTypeBadge,
  PageHeader,
  fmtDate
} from "@/components/ui";
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
        <Link
          href="/drafts"
          className="text-xs text-neutral-500 hover:text-neutral-800"
        >
          ← All drafts
        </Link>
        <Link
          href={`/opportunities/${draft.opportunity.id}`}
          className="text-xs text-neutral-500 hover:text-neutral-800"
        >
          Source opportunity →
        </Link>
      </div>

      <PageHeader
        eyebrow={`v${draft.version} · ${draft.draft_type.replaceAll("_", " ")}`}
        title={draft.title}
        subtitle={
          <span className="inline-flex items-center gap-2">
            <Badge tone={STATUS_TONE[draft.status]}>
              {STATUS_LABEL[draft.status]}
            </Badge>
            {draft.opportunity.notice_type && (
              <NoticeTypeBadge type={draft.opportunity.notice_type} />
            )}
            <span className="text-neutral-500">·</span>
            <span>{draft.opportunity.title}</span>
          </span>
        }
        trailing={
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={`/drafts/${draft.id}/export.docx`}
              className="rounded-md border border-brand-700 bg-brand-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-800"
              title="Download this draft as a Microsoft Word document"
            >
              ⬇ Export DOCX
            </a>
            {allowedStatuses.map((s) => (
              <form key={s} action={setDraftStatus}>
                <input type="hidden" name="id" value={draft.id} />
                <input type="hidden" name="status" value={s} />
                <button
                  type="submit"
                  className={
                    s === "submitted"
                      ? "rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                      : "rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:border-neutral-500"
                  }
                >
                  Mark {STATUS_LABEL[s].toLowerCase()}
                </button>
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
              <button
                type="submit"
                className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs text-neutral-500 hover:border-red-300 hover:text-red-700"
                title="Delete this draft permanently"
              >
                Delete
              </button>
            </form>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Editor — full width on small, 2/3 on large */}
        <section className="lg:col-span-2">
          <form action={updateAction} className="space-y-3">
            <label className="block">
              <span className="block text-[11px] uppercase tracking-wider text-neutral-500">
                Title
              </span>
              <input
                name="title"
                defaultValue={draft.title}
                className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-neutral-500 focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="block text-[11px] uppercase tracking-wider text-neutral-500">
                Draft content (markdown)
              </span>
              <textarea
                name="content"
                defaultValue={draft.content}
                rows={36}
                className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-3 font-mono text-[13px] leading-relaxed shadow-sm focus:border-neutral-500 focus:outline-none"
              />
            </label>
            <div className="flex items-center justify-end gap-2">
              <Link
                href="/drafts"
                className="rounded-md border border-neutral-300 px-3 py-2 text-sm hover:border-neutral-500"
              >
                Cancel
              </Link>
              <button
                type="submit"
                className="rounded-md border border-neutral-900 bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
              >
                Save changes
              </button>
            </div>
          </form>
        </section>

        {/* Side panel — generation metadata + regenerate form */}
        <aside className="space-y-4">
          <div className="rounded-md border border-neutral-200 bg-white p-4">
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">
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
                    className="text-blue-700 hover:underline"
                  >
                    v{draft.version - 1}
                  </Link>
                </Row>
              )}
              {draft.created_by && (
                <Row label="Author">
                  {draft.created_by.full_name}{" "}
                  <span className="text-neutral-500">
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

          <div className="rounded-md border border-neutral-200 bg-white p-4">
            <p className="text-[11px] uppercase tracking-wider text-neutral-500">
              Regenerate
            </p>
            <p className="mt-2 text-xs text-neutral-600">
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
      <dt className="text-[11px] uppercase tracking-wider text-neutral-500">
        {label}
      </dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}
