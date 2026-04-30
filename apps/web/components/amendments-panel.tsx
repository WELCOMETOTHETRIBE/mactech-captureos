import { Badge, Card, fmtDate } from "@/components/ui";
import type { AmendmentListOut, AmendmentOut } from "@/lib/api";

type Props = {
  amendments: AmendmentListOut | null;
};

const FIELD_LABELS: Record<string, string> = {
  title: "Title",
  response_deadline: "Response deadline",
  posted_at: "Posted date",
  estimated_value_low: "Est. value (low)",
  estimated_value_high: "Est. value (high)",
  naics_code: "NAICS",
  set_aside: "Set-aside",
  notice_type: "Notice type",
  description_text: "Description",
};

export function AmendmentsPanel({ amendments }: Props) {
  if (!amendments || amendments.amendments.length === 0) {
    return null;
  }
  return (
    <Card
      title={`Amendments (${amendments.amendments.length})`}
      trailing={
        <Badge tone="amber">
          opportunity changed since first ingest
        </Badge>
      }
    >
      <div className="space-y-4">
        {amendments.amendments.map((a) => (
          <AmendmentEntry key={a.id} amendment={a} />
        ))}
      </div>
    </Card>
  );
}

function AmendmentEntry({ amendment }: { amendment: AmendmentOut }) {
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50/40 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-amber-900">
          Amendment detected {fmtDate(amendment.detected_at)}
        </p>
        <span className="text-[11px] text-neutral-500">
          {amendment.diff_summary.length} field
          {amendment.diff_summary.length === 1 ? "" : "s"} changed
        </span>
      </div>
      {amendment.diff_summary.length > 0 && (
        <ul className="mt-2 divide-y divide-amber-100">
          {amendment.diff_summary.map((d, i) => (
            <li key={i} className="py-2">
              <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
                {FIELD_LABELS[d.field] ?? d.field}
              </p>
              <div className="mt-1 grid grid-cols-1 gap-2 text-xs md:grid-cols-2">
                <div>
                  <span className="text-[10px] uppercase text-neutral-400">
                    Before
                  </span>
                  <DiffValue value={d.before} />
                </div>
                <div>
                  <span className="text-[10px] uppercase text-neutral-400">
                    After
                  </span>
                  <DiffValue value={d.after} />
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DiffValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return (
      <p className="mt-0.5 italic text-neutral-400">(none)</p>
    );
  }
  const display =
    typeof value === "string" || typeof value === "number"
      ? String(value)
      : JSON.stringify(value);
  return (
    <p className="mt-0.5 whitespace-pre-wrap break-words text-neutral-800">
      {display}
    </p>
  );
}
