import Link from "next/link";
import { notFound } from "next/navigation";
import { CapabilityStatementForm } from "@/components/library-forms";
import { PageHeader } from "@/components/ui";
import { apiFetch, type CapabilityStatementOut } from "@/lib/api";
import { updateCapabilityStatement } from "@/lib/library-actions";

export const dynamic = "force-dynamic";

export default async function EditCapabilityStatementPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let cs: CapabilityStatementOut;
  try {
    cs = await apiFetch<CapabilityStatementOut>(`/capability-statements/${id}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  const action = updateCapabilityStatement.bind(null, id);

  return (
    <div className="space-y-6">
      <Link
        href="/library"
        className="text-xs text-neutral-500 hover:text-neutral-800"
      >
        ← Library
      </Link>
      <PageHeader
        eyebrow="Capability statements"
        title="Edit capability cluster"
        subtitle={
          <span>
            {cs.title}
            {!cs.has_embedding && (
              <span className="ml-2 inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                no embedding yet — worker picks it up next 15-min tick
              </span>
            )}
          </span>
        }
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <CapabilityStatementForm
          action={action}
          initial={cs}
          submitLabel="Save changes"
        />
      </div>
    </div>
  );
}
