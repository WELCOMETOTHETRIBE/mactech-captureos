import Link from "next/link";
import { notFound } from "next/navigation";
import { TeamingPartnerForm } from "@/components/library-forms";
import { PageHeader } from "@/components/ui";
import { apiFetch, type TeamingPartnerOut } from "@/lib/api";
import { updateTeamingPartner } from "@/lib/library-actions";

export const dynamic = "force-dynamic";

export default async function EditTeamingPartnerPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let p: TeamingPartnerOut;
  try {
    p = await apiFetch<TeamingPartnerOut>(`/teaming-partners/${id}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    throw err;
  }

  const action = updateTeamingPartner.bind(null, id);

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
        title="Edit partner"
        subtitle={p.name}
      />
      <div className="rounded-md border border-neutral-200 bg-white p-6">
        <TeamingPartnerForm
          action={action}
          initial={p}
          submitLabel="Save changes"
        />
      </div>
    </div>
  );
}
