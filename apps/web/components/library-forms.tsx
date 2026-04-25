import type { ReactNode } from "react";
import type { PastPerformanceOut, TeamingPartnerOut } from "@/lib/api";

const ROLE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "prime", label: "Prime contractor" },
  { value: "sub", label: "Subcontractor" },
  { value: "joint_venture", label: "Joint venture" },
  { value: "individual", label: "Individual / pre-firm experience" }
];

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive (archived)" }
];

export function PastPerformanceForm({
  action,
  initial,
  submitLabel
}: {
  action: (formData: FormData) => Promise<void>;
  initial?: PastPerformanceOut;
  submitLabel: string;
}) {
  return (
    <form action={action} className="space-y-5">
      <FormField
        label="Engagement title"
        hint="The contract or engagement name. Used as a unique identifier within your tenant."
      >
        <input
          name="title"
          required
          maxLength={255}
          defaultValue={initial?.title ?? ""}
          placeholder="e.g. VA Cybersecurity Operations Support FY24"
          className={inputCls}
        />
      </FormField>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Customer agency">
          <input
            name="customer_agency"
            maxLength={255}
            defaultValue={initial?.customer_agency ?? ""}
            placeholder="e.g. Department of Veterans Affairs"
            className={inputCls}
          />
        </FormField>
        <FormField label="Customer office (optional)">
          <input
            name="customer_office"
            maxLength={255}
            defaultValue={initial?.customer_office ?? ""}
            placeholder="e.g. VISN 5"
            className={inputCls}
          />
        </FormField>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="Contract number">
          <input
            name="contract_number"
            maxLength={64}
            defaultValue={initial?.contract_number ?? ""}
            placeholder="e.g. 36C24E25P0123"
            className={`${inputCls} font-mono text-xs`}
          />
        </FormField>
        <FormField label="NAICS code">
          <input
            name="naics_code"
            maxLength={8}
            defaultValue={initial?.naics_code ?? ""}
            placeholder="e.g. 541512"
            className={`${inputCls} font-mono text-xs`}
          />
        </FormField>
        <FormField label="Role">
          <select
            name="role"
            defaultValue={initial?.role ?? "prime"}
            className={inputCls}
          >
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="Period start">
          <input
            type="date"
            name="period_start"
            defaultValue={initial?.period_start ?? ""}
            className={inputCls}
          />
        </FormField>
        <FormField label="Period end">
          <input
            type="date"
            name="period_end"
            defaultValue={initial?.period_end ?? ""}
            className={inputCls}
          />
        </FormField>
        <FormField label="Contract value (USD)">
          <input
            type="number"
            step="any"
            name="contract_value"
            defaultValue={initial?.contract_value ?? ""}
            placeholder="2400000"
            className={`${inputCls} tabular-nums`}
          />
        </FormField>
      </div>

      <FormField
        label="Narrative summary"
        hint="2–4 sentences describing scope, outcomes, and tools. Cited verbatim by the proposal drafter — write it the way you'd want a CO to read it."
      >
        <textarea
          name="summary"
          required
          rows={6}
          defaultValue={initial?.summary ?? ""}
          placeholder="Provided continuous monitoring and incident response support for VA's cybersecurity operations..."
          className={`${inputCls} font-sans leading-relaxed`}
        />
      </FormField>

      <FormField
        label="Keywords"
        hint="Comma-separated. Used by the drafter to match this engagement against opportunity keywords."
      >
        <input
          name="keywords"
          defaultValue={(initial?.keywords ?? []).join(", ")}
          placeholder="ATO, RMF, ConMon, incident response, NIST 800-53"
          className={inputCls}
        />
      </FormField>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField
          label="Related capability statement slugs"
          hint="Comma-separated slugs from the capability statements above."
        >
          <input
            name="related_capability_slugs"
            defaultValue={(initial?.related_capability_slugs ?? []).join(", ")}
            placeholder="rmf-ato-support, conmon"
            className={`${inputCls} font-mono text-xs`}
          />
        </FormField>
        <FormField
          label="Related founder slugs"
          hint="Comma-separated. Which founders led this engagement?"
        >
          <input
            name="related_founder_slugs"
            defaultValue={(initial?.related_founder_slugs ?? []).join(", ")}
            placeholder="patrick-caruso, james-adams"
            className={`${inputCls} font-mono text-xs`}
          />
        </FormField>
      </div>

      <FormActions submitLabel={submitLabel} />
    </form>
  );
}

export function TeamingPartnerForm({
  action,
  initial,
  submitLabel
}: {
  action: (formData: FormData) => Promise<void>;
  initial?: TeamingPartnerOut;
  submitLabel: string;
}) {
  return (
    <form action={action} className="space-y-5">
      <FormField label="Partner name">
        <input
          name="name"
          required
          maxLength={255}
          defaultValue={initial?.name ?? ""}
          placeholder="e.g. Acme Federal Solutions, LLC"
          className={inputCls}
        />
      </FormField>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="UEI (optional)">
          <input
            name="uei"
            maxLength={16}
            defaultValue={initial?.uei ?? ""}
            placeholder="12-character UEI"
            className={`${inputCls} font-mono text-xs`}
          />
        </FormField>
        <FormField label="CAGE code (optional)">
          <input
            name="cage_code"
            maxLength={8}
            defaultValue={initial?.cage_code ?? ""}
            placeholder="e.g. 0ABCD"
            className={`${inputCls} font-mono text-xs`}
          />
        </FormField>
        <FormField label="Status">
          <select
            name="status"
            defaultValue={initial?.status ?? "active"}
            className={inputCls}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <FormField
        label="Capabilities"
        hint="Comma-separated. What does this partner bring to a joint pursuit?"
      >
        <input
          name="capabilities"
          defaultValue={(initial?.capabilities ?? []).join(", ")}
          placeholder="cloud migration, FedRAMP support, IT staffing"
          className={inputCls}
        />
      </FormField>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField
          label="NAICS codes"
          hint="Comma-separated 6-digit codes."
        >
          <input
            name="naics_codes"
            defaultValue={(initial?.naics_codes ?? []).join(", ")}
            placeholder="541512, 541519"
            className={`${inputCls} font-mono text-xs`}
          />
        </FormField>
        <FormField
          label="Set-aside certifications"
          hint="Comma-separated. e.g. SDVOSB, 8(a), HUBZone, WOSB."
        >
          <input
            name="set_aside_certifications"
            defaultValue={(initial?.set_aside_certifications ?? []).join(", ")}
            placeholder="SDVOSB, 8(a)"
            className={inputCls}
          />
        </FormField>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Contact name">
          <input
            name="contact_name"
            maxLength={255}
            defaultValue={initial?.contact_name ?? ""}
            placeholder="e.g. Jane Smith, BD lead"
            className={inputCls}
          />
        </FormField>
        <FormField label="Contact email">
          <input
            type="email"
            name="contact_email"
            maxLength={255}
            defaultValue={initial?.contact_email ?? ""}
            placeholder="jane@acme.com"
            className={inputCls}
          />
        </FormField>
      </div>

      <FormField
        label="Notes"
        hint="Free-form. Capture-team conversations, prior collaboration history, redlines."
      >
        <textarea
          name="notes"
          rows={4}
          defaultValue={initial?.notes ?? ""}
          placeholder="Worked with us on the FY23 VA pursuit; their FedRAMP-Mod ATO is current."
          className={`${inputCls} leading-relaxed`}
        />
      </FormField>

      <FormActions submitLabel={submitLabel} />
    </form>
  );
}

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
      {hint && (
        <span className="mb-1 mt-0.5 block text-xs text-neutral-500">{hint}</span>
      )}
      <div className={hint ? "mt-1" : "mt-1.5"}>{children}</div>
    </label>
  );
}

function FormActions({ submitLabel }: { submitLabel: string }) {
  return (
    <div className="flex items-center justify-end gap-2 border-t border-neutral-200 pt-4">
      <a
        href="/library"
        className="rounded-md border border-neutral-300 px-4 py-2 text-sm hover:border-neutral-500"
      >
        Cancel
      </a>
      <button
        type="submit"
        className="rounded-md border border-neutral-900 bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
      >
        {submitLabel}
      </button>
    </div>
  );
}
