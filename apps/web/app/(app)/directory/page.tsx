import {
  apiFetch,
  type DirectoryContactList,
  type DirectoryOrganizationList
} from "@/lib/api";
import { Badge, Card, EmptyState, LinkButton, PageHeader } from "@/components/ui";

export const dynamic = "force-dynamic";

/**
 * The MacTech shared company directory — people and organizations, internal
 * and external — served from bizops over the suite service API. Capture is a
 * consumer: it reads and adds contacts, bizops remains the system of record.
 */
export default async function DirectoryPage({
  searchParams
}: {
  searchParams: { q?: string; kind?: string };
}) {
  const q = (searchParams.q ?? "").trim();
  const kind = searchParams.kind === "INTERNAL" || searchParams.kind === "EXTERNAL" ? searchParams.kind : "";

  let contacts: DirectoryContactList | null = null;
  let organizations: DirectoryOrganizationList | null = null;
  let unavailable = false;
  try {
    const contactParams = new URLSearchParams();
    if (q) contactParams.set("q", q);
    if (kind) contactParams.set("kind", kind);
    const qs = contactParams.toString();
    [contacts, organizations] = await Promise.all([
      apiFetch<DirectoryContactList>(`/directory/contacts${qs ? `?${qs}` : ""}`),
      apiFetch<DirectoryOrganizationList>("/directory/organizations")
    ]);
  } catch {
    unavailable = true;
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Shared across MacTech apps"
        title="Directory"
        subtitle="The company address book — internal teammates and external contracting contacts. Managed in BizOps; every MacTech app reads and contributes to the same list."
      />

      {unavailable ? (
        <EmptyState
          title="Directory unavailable"
          body="The shared directory (served by BizOps) could not be reached. Try again shortly — nothing in Capture is affected."
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <form className="flex flex-wrap items-center gap-2" action="/directory" method="get">
              <input
                type="search"
                name="q"
                defaultValue={q}
                placeholder="Search people…"
                aria-label="Search people"
                className="w-56 rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-neutral-500 focus:outline-none"
              />
              <select
                name="kind"
                defaultValue={kind}
                aria-label="Filter internal or external"
                className="rounded-md border border-neutral-300 px-2 py-2 text-sm shadow-sm"
              >
                <option value="">Everyone</option>
                <option value="EXTERNAL">External</option>
                <option value="INTERNAL">Internal</option>
              </select>
              <button
                type="submit"
                className="rounded-md border border-neutral-300 px-3 py-2 text-sm font-semibold hover:bg-neutral-50"
              >
                Filter
              </button>
            </form>
            <div className="ml-auto flex gap-2">
              <LinkButton href="/directory/organizations/new" variant="secondary">
                Add organization
              </LinkButton>
              <LinkButton href="/directory/new" variant="primary">Add contact</LinkButton>
            </div>
          </div>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-neutral-800">
              People ({contacts?.total ?? 0})
            </h2>
            {!contacts || contacts.items.length === 0 ? (
              <EmptyState
                title="No people found"
                body={
                  q || kind
                    ? "No directory contacts match this filter."
                    : "Add the contracting officers, primes, and teammates your pursuits touch — every MacTech app will see them."
                }
              />
            ) : (
              <Card>
                <ul className="divide-y divide-neutral-100">
                  {contacts.items.map((c) => (
                    <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-neutral-900">{c.name}</p>
                        <p className="truncate text-xs text-neutral-500">
                          {[c.title, c.organization_name].filter(Boolean).join(" · ") || "—"}
                        </p>
                      </div>
                      <Badge tone={c.kind === "INTERNAL" ? "green" : "blue"}>
                        {c.kind === "INTERNAL" ? "Internal" : "External"}
                      </Badge>
                      <div className="w-56 truncate text-right text-xs text-neutral-500">
                        {c.email ? (
                          <a href={`mailto:${c.email}`} className="hover:text-neutral-800">
                            {c.email}
                          </a>
                        ) : (
                          c.phone ?? "—"
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-neutral-800">
              Organizations ({organizations?.total ?? 0})
            </h2>
            {!organizations || organizations.items.length === 0 ? (
              <EmptyState title="No organizations yet" body="Add agencies, primes, and vendors once — reuse them everywhere." />
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {organizations.items.map((o) => (
                  <Card key={o.id}>
                    <div className="p-4">
                      <p className="truncate text-sm font-semibold text-neutral-900">{o.name}</p>
                      <p className="text-xs text-neutral-500">
                        {o.org_type.toLowerCase().replaceAll("_", " ")}
                        {o.abbreviation ? ` · ${o.abbreviation}` : ""}
                      </p>
                      <p className="mt-1 text-xs text-neutral-400">
                        {typeof o.contact_count === "number" ? `${o.contact_count} contacts` : ""}
                        {o.uei ? ` · UEI ${o.uei}` : ""}
                      </p>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </section>

          <p className="text-xs text-neutral-400">
            Records added here are written to the shared MacTech directory (source app
            “capture”). Edit and archive in BizOps.
          </p>
        </>
      )}
    </div>
  );
}
