import Link from "next/link";
import { PastPerformanceForm } from "@/components/library-forms";
import { PageHeader } from "@/components/ui";
import { createPastPerformance } from "@/lib/library-actions";

export const dynamic = "force-dynamic";

export default function NewPastPerformancePage() {
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
        title="Add a record"
        subtitle="Each record becomes a citation the Phase 3 proposal drafter can pull from. Be specific about scope, outcomes, and tools."
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <PastPerformanceForm action={createPastPerformance} submitLabel="Create record" />
      </div>
    </div>
  );
}
