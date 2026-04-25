import Link from "next/link";
import { notFound } from "next/navigation";
import { PastPerformanceForm } from "@/components/library-forms";
import { PageHeader } from "@/components/ui";
import { apiFetch, type PastPerformanceOut } from "@/lib/api";
import { updatePastPerformance } from "@/lib/library-actions";

export const dynamic = "force-dynamic";

export default async function EditPastPerformancePage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let pp: PastPerformanceOut;
  try {
    pp = await apiFetch<PastPerformanceOut>(`/past-performance/${id}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  const action = updatePastPerformance.bind(null, id);

  return (
    <div className="space-y-6">
      <Link
        href="/library"
        className="text-xs text-neutral-500 hover:text-neutral-800"
      >
        ← Library
      </Link>
      <PageHeader
        eyebrow="Past performance"
        title="Edit record"
        subtitle={pp.title}
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <PastPerformanceForm
          action={action}
          initial={pp}
          submitLabel="Save changes"
        />
      </div>
    </div>
  );
}
