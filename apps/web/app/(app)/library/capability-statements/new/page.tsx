import Link from "next/link";
import { CapabilityStatementForm } from "@/components/library-forms";
import { PageHeader } from "@/components/ui";
import { createCapabilityStatement } from "@/lib/library-actions";

export const dynamic = "force-dynamic";

export default function NewCapabilityStatementPage() {
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
        title="Add a capability cluster"
        subtitle={
          <span>
            Each capability statement becomes a citation the proposal drafter
            uses + a vector match candidate when scoring opportunities. Be
            specific about scope, frameworks, and outcomes.
          </span>
        }
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <CapabilityStatementForm
          action={createCapabilityStatement}
          submitLabel="Create capability statement"
        />
      </div>
    </div>
  );
}
