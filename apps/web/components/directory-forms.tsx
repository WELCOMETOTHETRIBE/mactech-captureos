import type { ReactNode } from "react";
import type { DirectoryOrganizationOut } from "@/lib/api";

/**
 * Forms for the shared company directory. The closed vocabularies here
 * (kind, org type) mirror the bizops Directory enums exactly — bizops
 * rejects anything outside them, so keep the two lists in sync.
 */

const KIND_OPTIONS = [
  { value: "EXTERNAL", label: "External contact" },
  { value: "INTERNAL", label: "Internal (MacTech)" }
];

const ORG_TYPE_OPTIONS = [
  { value: "GOVERNMENT", label: "Government" },
  { value: "PRIME", label: "Prime" },
  { value: "SUBCONTRACTOR", label: "Subcontractor" },
  { value: "TEAMING_PARTNER", label: "Teaming partner" },
  { value: "VENDOR", label: "Vendor" },
  { value: "CONSULTANT", label: "Consultant" },
  { value: "INTERNAL", label: "Internal (MacTech)" },
  { value: "OTHER", label: "Other" }
];

const inputCls =
  "w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-neutral-500 focus:outline-none focus:ring-0";

function FormField({
  label,
  hint,
  children
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-[11px] uppercase tracking-wider text-neutral-600">
        {label}
      </span>
      {hint && <span className="block text-xs text-neutral-400">{hint}</span>}
      <div className="mt-1">{children}</div>
    </label>
  );
}

export function DirectoryContactForm({
  action,
  organizations,
  submitLabel
}: {
  action: (formData: FormData) => Promise<void>;
  organizations: DirectoryOrganizationOut[];
  submitLabel: string;
}) {
  return (
    <form action={action} className="space-y-5">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Name">
          <input name="name" required maxLength={200} placeholder="e.g. Jane Doe" className={inputCls} />
        </FormField>
        <FormField label="Kind">
          <select name="kind" defaultValue="EXTERNAL" className={inputCls}>
            {KIND_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Title (optional)">
          <input name="title" placeholder="e.g. Contracting Officer" className={inputCls} />
        </FormField>
        <FormField label="Department (optional)">
          <input name="department" className={inputCls} />
        </FormField>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Organization" hint="Pick a directory organization, or use free text below.">
          <select name="organization_id" defaultValue="" className={inputCls}>
            <option value="">— none —</option>
            {organizations.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </FormField>
        <FormField label="Organization free text (optional)">
          <input name="organization_name" className={inputCls} />
        </FormField>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="Email (optional)">
          <input name="email" type="email" className={inputCls} />
        </FormField>
        <FormField label="Phone (optional)">
          <input name="phone" className={inputCls} />
        </FormField>
        <FormField label="Mobile (optional)">
          <input name="mobile" className={inputCls} />
        </FormField>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="LinkedIn (optional)">
          <input name="linkedin_url" placeholder="https://linkedin.com/in/…" className={inputCls} />
        </FormField>
        <FormField label="Tags" hint="Comma-separated, e.g. contracting, ko">
          <input name="tags" className={inputCls} />
        </FormField>
      </div>

      <FormField label="Notes (optional)">
        <textarea name="notes" rows={3} className={inputCls} />
      </FormField>

      <button
        type="submit"
        className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-semibold text-white hover:bg-neutral-700"
      >
        {submitLabel}
      </button>
    </form>
  );
}

export function DirectoryOrganizationForm({
  action,
  submitLabel
}: {
  action: (formData: FormData) => Promise<void>;
  submitLabel: string;
}) {
  return (
    <form action={action} className="space-y-5">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Name">
          <input name="name" required maxLength={200} placeholder="e.g. Naval Air Systems Command" className={inputCls} />
        </FormField>
        <FormField label="Type">
          <select name="org_type" defaultValue="OTHER" className={inputCls}>
            {ORG_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="Abbreviation (optional)">
          <input name="abbreviation" placeholder="e.g. NAVAIR" className={inputCls} />
        </FormField>
        <FormField label="UEI (optional)">
          <input name="uei" maxLength={16} className={`${inputCls} font-mono text-xs`} />
        </FormField>
        <FormField label="CAGE code (optional)">
          <input name="cage_code" maxLength={8} className={`${inputCls} font-mono text-xs`} />
        </FormField>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="Website (optional)">
          <input name="website" placeholder="https://…" className={inputCls} />
        </FormField>
        <FormField label="Email (optional)">
          <input name="email" type="email" className={inputCls} />
        </FormField>
        <FormField label="Phone (optional)">
          <input name="phone" className={inputCls} />
        </FormField>
      </div>

      <FormField label="Tags" hint="Comma-separated">
        <input name="tags" className={inputCls} />
      </FormField>

      <FormField label="Notes (optional)">
        <textarea name="notes" rows={3} className={inputCls} />
      </FormField>

      <button
        type="submit"
        className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-semibold text-white hover:bg-neutral-700"
      >
        {submitLabel}
      </button>
    </form>
  );
}
