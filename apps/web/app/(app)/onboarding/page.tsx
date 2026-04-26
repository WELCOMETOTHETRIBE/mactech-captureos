import Link from "next/link";
import {
  apiFetch,
  type FoundersListResponse,
  type MeResponse
} from "@/lib/api";
import { lookupAndPrefill, saveFirmDetails } from "@/lib/onboarding";
import { Badge, NaicsBadge, PageHeader, Pillar } from "@/components/ui";

export const dynamic = "force-dynamic";

const SET_ASIDE_OPTIONS: Array<{ code: string; label: string; hint: string }> = [
  {
    code: "SDVOSB",
    label: "SDVOSB",
    hint: "Service-Disabled Veteran-Owned Small Business"
  },
  { code: "VOSB", label: "VOSB", hint: "Veteran-Owned Small Business" },
  { code: "WOSB", label: "WOSB", hint: "Women-Owned Small Business" },
  {
    code: "EDWOSB",
    label: "EDWOSB",
    hint: "Economically Disadvantaged Women-Owned Small Business"
  },
  { code: "8(a)", label: "8(a)", hint: "SBA 8(a) Business Development program" },
  { code: "HUBZone", label: "HUBZone", hint: "Historically Underutilized Business Zone" },
  { code: "SDB", label: "SDB", hint: "Small Disadvantaged Business" },
  { code: "SB", label: "SB", hint: "Small Business" }
];

export default async function OnboardingPage({
  searchParams
}: {
  searchParams: Promise<{
    uei?: string;
    legal_name?: string;
    cage_code?: string;
    set_asides?: string;
    naics?: string;
    error?: string;
  }>;
}) {
  const sp = await searchParams;
  const [me, foundersList] = await Promise.all([
    apiFetch<MeResponse>("/me"),
    apiFetch<FoundersListResponse>("/founders").catch(
      () => ({ total: 0, items: [] }) as FoundersListResponse
    )
  ]);

  const lookupError = sp.error ?? null;
  const prefillUei = sp.uei ?? me.tenant.uei ?? "";
  const prefillCage = sp.cage_code ?? me.tenant.cage_code ?? "";
  const prefillName = sp.legal_name ?? me.tenant.name ?? "";
  const prefillSetAsides =
    sp.set_asides
      ?.split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0) ?? me.tenant.set_aside_certifications ?? [];

  // NAICS suggested by SAM (from query params after lookup) and the codes
  // the tenant has already saved as targets. Union them so the checkbox
  // grid shows the merged set with appropriate `checked` state.
  const naicsFromSam =
    sp.naics
      ?.split(",")
      .map((s) => s.trim())
      .filter((s) => /^\d{2,8}$/.test(s)) ?? [];
  const tenantTargetNaics = me.tenant.target_naics ?? [];
  const naicsAllSuggested = Array.from(
    new Set([...tenantTargetNaics, ...naicsFromSam])
  );
  const fromLookup = sp.uei !== undefined && !lookupError;

  const isComplete = me.tenant.onboarding_completed_at !== null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Setup"
        title={isComplete ? "Tenant settings" : "Welcome — let's set up your firm"}
        subtitle={
          isComplete ? (
            <span>
              Your tenant is configured. You can update firm details below at
              any time.
            </span>
          ) : (
            <span>
              Two minutes. We&rsquo;ll pull your registered firm info from
              SAM.gov, then you confirm set-aside certifications. NAICS picker
              and founder roster ship in a follow-up sprint — for now, defaults
              come from your seeded config.
            </span>
          )
        }
        trailing={
          isComplete ? (
            <Badge tone="green">complete</Badge>
          ) : (
            <Badge tone="amber">incomplete</Badge>
          )
        }
      />

      {/* Step 1 — UEI lookup */}
      <section className="rounded-lg border border-neutral-200 bg-white p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-brand-700">
          1 · Look up your UEI
        </h2>
        <p className="mt-1 text-sm text-neutral-600">
          Type your 12-character SAM.gov UEI. We&rsquo;ll fetch your registered
          legal name, CAGE code, and any small-business / veteran / women-owned
          / 8(a) / HUBZone certifications on file.
        </p>
        <form action={lookupAndPrefill} className="mt-4 flex flex-wrap items-end gap-2">
          <label className="block min-w-0 flex-1">
            <span className="block text-[11px] uppercase tracking-wide text-neutral-500">
              UEI (12 chars)
            </span>
            <input
              name="uei"
              defaultValue={prefillUei}
              maxLength={16}
              placeholder="e.g. ABC123XYZ987"
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 font-mono text-sm uppercase shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </label>
          <button
            type="submit"
            className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
          >
            Look up →
          </button>
        </form>
        {lookupError && (
          <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <span className="font-medium">Lookup failed.</span> {lookupError}
            <br />
            You can still type the firm details manually below.
          </p>
        )}
        {fromLookup && (
          <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
            <span className="font-medium">Pulled from SAM.gov.</span> Review and
            edit below before saving.
            {naicsFromSam.length > 0 && (
              <p className="mt-1 text-xs">
                NAICS on file ({naicsFromSam.length}):{" "}
                {naicsFromSam.slice(0, 6).join(", ")}
                {naicsFromSam.length > 6 && ` (+${naicsFromSam.length - 6} more)`}
              </p>
            )}
          </div>
        )}
      </section>

      {/* Step 2 — Confirm firm details + certifications */}
      <section className="rounded-lg border border-neutral-200 bg-white p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-brand-700">
          2 · Confirm your firm details
        </h2>
        <p className="mt-1 text-sm text-neutral-600">
          The drafter cites these in every Sources Sought response. Set-aside
          certifications drive how opportunities are scored against your fit
          profile.
        </p>

        <form action={saveFirmDetails} className="mt-4 space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <label className="block md:col-span-2">
              <span className="block text-[11px] uppercase tracking-wide text-neutral-500">
                Legal business name
              </span>
              <input
                name="legal_name"
                defaultValue={prefillName}
                maxLength={255}
                className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>
            <label className="block">
              <span className="block text-[11px] uppercase tracking-wide text-neutral-500">
                CAGE code
              </span>
              <input
                name="cage_code"
                defaultValue={prefillCage}
                maxLength={8}
                className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 font-mono text-sm uppercase shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>
          </div>
          {/* Hidden UEI passes through with the save — input above is read-only
              context; the actual value persisted is the UEI from the lookup. */}
          <input type="hidden" name="uei" value={prefillUei} />

          <fieldset>
            <legend className="text-[11px] uppercase tracking-wide text-neutral-500">
              Set-aside certifications
            </legend>
            <p className="mt-1 text-xs text-neutral-500">
              Check the ones the firm holds (active or pending). The proposal
              drafter cites these in every set-aside qualification statement.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
              {SET_ASIDE_OPTIONS.map((opt) => {
                const checked = prefillSetAsides.includes(opt.code);
                return (
                  <label
                    key={opt.code}
                    title={opt.hint}
                    className={`flex cursor-pointer items-center gap-2 rounded-md border p-3 text-sm transition-colors ${
                      checked
                        ? "border-brand-500 bg-brand-50 text-brand-900"
                        : "border-neutral-200 hover:border-neutral-400"
                    }`}
                  >
                    <input
                      type="checkbox"
                      name="set_aside_certifications"
                      value={opt.code}
                      defaultChecked={checked}
                      className="rounded border-neutral-400"
                    />
                    <span className="font-medium">{opt.label}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          {/* NAICS targets */}
          <fieldset>
            <legend className="text-[11px] uppercase tracking-wide text-neutral-500">
              NAICS targets
            </legend>
            <p className="mt-1 text-xs text-neutral-500">
              The opportunity-scoring engine ranks every SAM.gov notice
              against your NAICS list. Suggested codes come from your SAM
              registration; check the ones you actually want to pursue.
            </p>
            {naicsAllSuggested.length === 0 ? (
              <p className="mt-3 rounded-md border border-dashed border-neutral-300 bg-neutral-50 p-3 text-xs text-neutral-600">
                Look up your UEI above to populate suggested NAICS, or type
                codes manually below.
              </p>
            ) : (
              <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-4">
                {naicsAllSuggested.map((code) => {
                  const checked = tenantTargetNaics.includes(code);
                  return (
                    <label
                      key={code}
                      className={`flex cursor-pointer items-center gap-2 rounded-md border p-2 text-sm transition-colors ${
                        checked
                          ? "border-brand-500 bg-brand-50 text-brand-900"
                          : "border-neutral-200 hover:border-neutral-400"
                      }`}
                    >
                      <input
                        type="checkbox"
                        name="target_naics"
                        value={code}
                        defaultChecked={checked}
                        className="rounded border-neutral-400"
                      />
                      <span className="font-mono text-xs">{code}</span>
                    </label>
                  );
                })}
              </div>
            )}
            <label className="mt-3 block">
              <span className="text-[11px] text-neutral-500">
                Additional NAICS codes (comma-separated 6-digit codes)
              </span>
              <input
                name="target_naics_extra"
                placeholder="e.g. 541512, 541519, 541330"
                className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 font-mono text-xs shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>
          </fieldset>

          {/* Founder roster preview */}
          <div className="rounded-md border border-neutral-100 bg-neutral-50 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-[11px] uppercase tracking-wide text-neutral-500">
                Founder roster
                <span className="ml-2 font-normal lowercase text-neutral-400">
                  ({foundersList.total} on file)
                </span>
              </p>
              <Link
                href="/settings#founders"
                className="text-xs font-medium text-brand-700 hover:underline"
              >
                Manage in settings →
              </Link>
            </div>
            {foundersList.items.length > 0 ? (
              <ul className="mt-2 space-y-1 text-sm">
                {foundersList.items.slice(0, 6).map((f) => (
                  <li
                    key={f.id}
                    className="flex flex-wrap items-baseline justify-between gap-2"
                  >
                    <span className="text-neutral-800">
                      {f.full_name}{" "}
                      <span className="text-xs text-neutral-500">
                        — {f.title}
                      </span>
                    </span>
                    <Pillar pillar={f.pillar} />
                  </li>
                ))}
                {foundersList.items.length > 6 && (
                  <li className="text-xs text-neutral-500">
                    + {foundersList.items.length - 6} more
                  </li>
                )}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-neutral-500">
                No founders on file. Add a few in Settings so the proposal
                drafter can name your key personnel.
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-neutral-200 pt-4">
            <button
              type="submit"
              name="complete"
              value="0"
              className="rounded-md border border-neutral-300 px-4 py-2 text-sm hover:border-neutral-500"
            >
              Save (keep wizard open)
            </button>
            <button
              type="submit"
              name="complete"
              value="1"
              className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
            >
              Save &amp; finish setup →
            </button>
          </div>
        </form>
      </section>

      {/* What's next */}
      <section className="rounded-lg border border-neutral-200 bg-white p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-700">
          What&rsquo;s next
        </h2>
        <p className="mt-1 text-sm text-neutral-600">
          After saving, you&rsquo;ll have a fully-configured tenant. To get the
          most out of CaptureOS, also:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-neutral-700">
          <li>
            <Link
              href="/library/capability-statements/import"
              className="text-brand-700 hover:underline"
            >
              Drop a capability statement PDF
            </Link>{" "}
            so opportunities get scored against your real capabilities.
          </li>
          <li>
            <Link
              href="/library/past-performance/import"
              className="text-brand-700 hover:underline"
            >
              Import a past-performance write-up
            </Link>{" "}
            so the proposal drafter has citations to draw from.
          </li>
          <li>
            <Link
              href="/library#teaming-partners"
              className="text-brand-700 hover:underline"
            >
              Add a teaming partner or two
            </Link>{" "}
            for multi-vendor pursuits.
          </li>
          <li>
            <Link href="/dashboard" className="text-brand-700 hover:underline">
              Open the dashboard
            </Link>{" "}
            to see the morning digest of your top scored opportunities.
          </li>
        </ul>
      </section>
    </div>
  );
}
