import { Badge, Card, fmtDate } from "@/components/ui";
import type { BidDecision, PursuitDetailOut } from "@/lib/api";

type Props = {
  detail: PursuitDetailOut;
  action: (formData: FormData) => Promise<void>;
};

const DECISION_TONE: Record<BidDecision, "neutral" | "green" | "red" | "amber"> = {
  pending: "amber",
  bid: "green",
  no_bid: "red",
};

const DECISION_LABEL: Record<BidDecision, string> = {
  pending: "Pending",
  bid: "Bid",
  no_bid: "No-bid",
};

export function BidDecisionForm({ detail, action }: Props) {
  return (
    <Card
      title="Bid decision"
      trailing={
        <Badge tone={DECISION_TONE[detail.bid_decision]}>
          {DECISION_LABEL[detail.bid_decision]}
        </Badge>
      }
    >
      <form action={action} className="space-y-4">
        <fieldset>
          <legend className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
            Decision
          </legend>
          <div className="mt-2 flex flex-wrap gap-3 text-sm">
            <DecisionRadio
              value="pending"
              label="Pending — still evaluating"
              currentValue={detail.bid_decision}
            />
            <DecisionRadio
              value="bid"
              label="Bid — committed"
              currentValue={detail.bid_decision}
            />
            <DecisionRadio
              value="no_bid"
              label="No-bid"
              currentValue={detail.bid_decision}
            />
          </div>
        </fieldset>

        <label className="block">
          <span className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
            Rationale
          </span>
          <p className="mt-0.5 text-[11px] text-neutral-500">
            Why are we bidding (or not)? This is the structured memo
            ProposalOS sees in the Capture Package — distinct from free-form
            notes.
          </p>
          <textarea
            name="bid_rationale"
            defaultValue={detail.bid_rationale ?? ""}
            rows={5}
            placeholder={
              "Strong NAICS match, incumbent is small business with no recent " +
              "competitive wins. SDVOSB set-aside aligns with our cert. " +
              "Capacity available — Patrick can lead. Bid."
            }
            className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </label>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-neutral-100 pt-3">
          <div className="text-[11px] text-neutral-500">
            {detail.bid_decision !== "pending" && detail.bid_decided_at ? (
              <>
                Decided {fmtDate(detail.bid_decided_at)}
                {detail.bid_decided_by_user_email && (
                  <> by {detail.bid_decided_by_user_email}</>
                )}
              </>
            ) : (
              <span className="italic">No decision recorded yet.</span>
            )}
          </div>
          <button
            type="submit"
            className="rounded-md border border-brand-700 bg-brand-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-800"
          >
            Save decision
          </button>
        </div>
      </form>
    </Card>
  );
}

function DecisionRadio({
  value,
  label,
  currentValue,
}: {
  value: BidDecision;
  label: string;
  currentValue: BidDecision;
}) {
  return (
    <label className="inline-flex items-center gap-2">
      <input
        type="radio"
        name="bid_decision"
        value={value}
        defaultChecked={currentValue === value}
        className="h-4 w-4 border-neutral-300 text-brand-700 focus:ring-brand-500"
      />
      <span className="text-neutral-800">{label}</span>
    </label>
  );
}
