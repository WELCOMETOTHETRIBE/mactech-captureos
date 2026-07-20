import Link from "next/link";
import { DirectoryOrganizationForm } from "@/components/directory-forms";
import { PageHeader } from "@/components/ui";
import { createDirectoryOrganization } from "@/lib/directory-actions";

export const dynamic = "force-dynamic";

export default function NewDirectoryOrganizationPage() {
  return (
    <div className="space-y-6">
      <Link href="/directory" className="text-xs text-neutral-500 hover:text-neutral-800">
        ← Directory
      </Link>
      <PageHeader
        eyebrow="Shared directory"
        title="Add an organization"
        subtitle="Adds this company or agency to the MacTech-wide address book."
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <DirectoryOrganizationForm action={createDirectoryOrganization} submitLabel="Add organization" />
      </div>
    </div>
  );
}
