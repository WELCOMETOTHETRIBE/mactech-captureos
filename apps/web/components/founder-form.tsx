import type { FounderRecord } from "@/lib/api";

const PILLAR_OPTIONS = [
  { value: "security", label: "Security (cyber, RMF, ATO)" },
  { value: "infrastructure", label: "Infrastructure (cloud, network, IaC)" },
  { value: "quality", label: "Quality (ISO, audit, metrology)" },
  { value: "governance", label: "Governance (legal, compliance, risk)" },
  { value: "other", label: "Other" }
];

export function FounderForm({
  action,
  initial,
  submitLabel
}: {
  action: (formData: FormData) => Promise<void>;
  initial?: FounderRecord;
  submitLabel: string;
}) {
  return (
    <form action={action} className="space-y-5">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Full name" hint="As it appears on signed proposals.">
          <input
            name="full_name"
            required
            maxLength={255}
            defaultValue={initial?.full_name ?? ""}
            placeholder="e.g. Patrick Caruso"
            className={inputCls}
          />
        </Field>
        <Field
          label="Title"
          hint="Role at the firm. Cited in capability responses."
        >
          <input
            name="title"
            required
            maxLength={255}
            defaultValue={initial?.title ?? ""}
            placeholder="e.g. Director of Cyber Assurance"
            className={inputCls}
          />
        </Field>
      </div>

      <Field
        label="Pillar"
        hint="Primary domain. Drives opportunity routing — opps in the founder's pillar route to them by default."
      >
        <select
          name="pillar"
          defaultValue={initial?.pillar ?? "other"}
          className={inputCls}
        >
          {PILLAR_OPTIONS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Email" hint="For the morning digest. Optional.">
        <input
          type="email"
          name="email"
          maxLength={255}
          defaultValue={initial?.email ?? ""}
          placeholder="patrick@mactechsolutionsllc.com"
          className={inputCls}
        />
      </Field>

      <Field
        label="Bio"
        hint="One-paragraph backgrounder. Cited in the proposal drafter's key personnel section."
      >
        <textarea
          name="bio"
          rows={4}
          defaultValue={initial?.bio ?? ""}
          placeholder="Patrick has 20+ years in federal cybersecurity..."
          className={`${inputCls} leading-relaxed`}
        />
      </Field>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          name="digest_enabled"
          defaultChecked={initial?.digest_enabled ?? true}
          className="rounded border-neutral-400"
        />
        <span>Receive the morning digest email</span>
      </label>

      <div className="flex items-center justify-end gap-2 border-t border-neutral-200 pt-4">
        <a
          href="/settings#founders"
          className="rounded-md border border-neutral-300 px-4 py-2 text-sm hover:border-neutral-500"
        >
          Cancel
        </a>
        <button
          type="submit"
          className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
        >
          {submitLabel}
        </button>
      </div>
    </form>
  );
}

const inputCls =
  "w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

function Field({
  label,
  hint,
  children
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-[11px] uppercase tracking-wider text-neutral-600">
        {label}
      </span>
      {hint && (
        <span className="mb-1 mt-0.5 block text-xs text-neutral-500">
          {hint}
        </span>
      )}
      <div className={hint ? "mt-1" : "mt-1.5"}>{children}</div>
    </label>
  );
}
