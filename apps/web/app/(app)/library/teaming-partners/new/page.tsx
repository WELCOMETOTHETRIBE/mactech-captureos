import Link from "next/link";
import { TeamingPartnerForm } from "@/components/library-forms";
import { PageHeader } from "@/components/ui";
import { createTeamingPartner } from "@/lib/library-actions";

export const dynamic = "force-dynamic";

export default function NewTeamingPartnerPage() {
  return (
    <div className="space-y-6">
      <Link
        href="/library"
        className="text-xs text-neutral-500 hover:text-neutral-800"
      >
        ← Library
      </Link>
      <PageHeader
        eyebrow="Teaming partners"
        title="Add a partner"
        subtitle="Capture firm capabilities, NAICS, and set-aside certifications so the proposal drafter can suggest teaming arrangements per opportunity."
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <TeamingPartnerForm action={createTeamingPartner} submitLabel="Add partner" />
      </div>
    </div>
  );
}
