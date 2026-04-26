import Link from "next/link";
import { FounderForm } from "@/components/founder-form";
import { PageHeader } from "@/components/ui";
import { createFounder } from "@/lib/founders";

export const dynamic = "force-dynamic";

export default function NewFounderPage() {
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
        title="Add a founder"
        subtitle="Founder records drive opportunity routing, digest distribution, and the proposal drafter's key personnel section."
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <FounderForm action={createFounder} submitLabel="Add founder" />
      </div>
    </div>
  );
}
