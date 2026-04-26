import Link from "next/link";
import { notFound } from "next/navigation";
import { FounderForm } from "@/components/founder-form";
import { PageHeader } from "@/components/ui";
import { apiFetch, type FounderRecord } from "@/lib/api";
import { updateFounder } from "@/lib/founders";

export const dynamic = "force-dynamic";

export default async function EditFounderPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let founder: FounderRecord;
  try {
    founder = await apiFetch<FounderRecord>(`/founders/${id}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  const action = updateFounder.bind(null, founder.id);

  return (
    <div className="space-y-6">
      <Link
        href="/settings#founders"
        className="text-xs text-neutral-500 hover:text-neutral-800"
      >
        ← Settings
      </Link>
      <PageHeader
        eyebrow="Founders"
        title="Edit founder"
        subtitle={founder.full_name}
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <FounderForm
          action={action}
          initial={founder}
          submitLabel="Save changes"
        />
      </div>
    </div>
  );
}
