import Link from "next/link";
import { apiFetch, type DirectoryOrganizationList } from "@/lib/api";
import { DirectoryContactForm } from "@/components/directory-forms";
import { PageHeader } from "@/components/ui";
import { createDirectoryContact } from "@/lib/directory-actions";

export const dynamic = "force-dynamic";

export default async function NewDirectoryContactPage() {
  let organizations: DirectoryOrganizationList = { total: 0, items: [] };
  try {
    organizations = await apiFetch<DirectoryOrganizationList>("/directory/organizations");
  } catch {
    // Directory unreachable — the form still works with free-text organization.
  }

  return (
    <div className="space-y-6">
      <Link href="/directory" className="text-xs text-neutral-500 hover:text-neutral-800">
        ← Directory
      </Link>
      <PageHeader
        eyebrow="Shared directory"
        title="Add a contact"
        subtitle="Adds this person to the MacTech-wide address book (visible in BizOps and every suite app)."
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <DirectoryContactForm
          action={createDirectoryContact}
          organizations={organizations.items}
          submitLabel="Add contact"
        />
      </div>
    </div>
  );
}
