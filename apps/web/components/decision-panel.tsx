import type { DecisionBlock } from "@/lib/api";

const LANE_LABELS: Record<string, string> = {
  PRIME_NOW: "Prime now",
  PRIME_WITH_PARTNER: "Prime with partner",
  SUB_TO_IDENTIFIED_PRIME: "Sub to identified prime",
  SUB_TO_PRIME_NOT_YET_IDENTIFIED: "Sub to prime (not yet identified)",
  SHAPE_EARLY: "Shape early",
  WATCH: "Watch",
  NO_BID: "No bid",
};

// Sober, GovCon-native styling. Prime lanes lead; NO_BID reads muted.
function laneClasses(lane: string): string {
  if (lane.startsWith("PRIME")) return "border-emerald-600/40 bg-emerald-950/20 text-emerald-300";
  if (lane.startsWith("SUB")) return "border-sky-600/40 bg-sky-950/20 text-sky-300";
  if (lane === "SHAPE_EARLY") return "border-amber-600/40 bg-amber-950/20 text-amber-300";
  if (lane === "NO_BID") return "border-border bg-muted/30 text-muted-foreground";
  return "border-border bg-card text-foreground";
}

const DIMENSIONS: [keyof DecisionBlock["vector"], string][] = [
  ["relevance", "Relevance"],
  ["prime_fit", "Prime fit"],
  ["subcontract_fit", "Sub fit"],
  ["winability", "Winability"],
  ["deliverability", "Deliverability"],
  ["strategic_value", "Strategic value"],
  ["urgency", "Urgency"],
  ["evidence_completeness", "Evidence completeness"],
];

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums font-medium">{value}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-foreground/60"
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

export function DecisionPanel({ decision }: { decision: DecisionBlock }) {
  const lane = decision.pursuit_lane;
  const hardGates = decision.gates.filter((g) => g.severity === "hard" && g.status === "fail");
  const softGates = decision.gates.filter((g) => !(g.severity === "hard" && g.status === "fail"));

  return (
    <section className="rounded-md border border-border bg-card p-5 space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`rounded-md border px-3 py-1 text-sm font-semibold ${laneClasses(lane)}`}
        >
          {LANE_LABELS[lane] ?? lane}
        </span>
        <span className="text-sm text-muted-foreground">
          Overall priority{" "}
          <span className="tabular-nums font-medium text-foreground">
            {decision.vector.overall_priority}
          </span>
        </span>
        <span className="text-xs text-muted-foreground">
          confidence: {decision.confidence}
        </span>
        {decision.needs_human_review && (
          <span className="rounded-md border border-amber-600/40 bg-amber-950/20 px-2 py-0.5 text-xs text-amber-300">
            Needs human review
          </span>
        )}
      </div>

      {decision.reason_codes.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {decision.reason_codes.map((rc) => (
            <span
              key={rc}
              className="rounded border border-border px-2 py-0.5 text-xs text-muted-foreground"
            >
              {rc}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        {DIMENSIONS.map(([key, label]) => (
          <Meter key={key} label={label} value={decision.vector[key]} />
        ))}
      </div>

      {(hardGates.length > 0 || softGates.length > 0) && (
        <div className="space-y-2 border-t border-border pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Gates &amp; blockers
          </h4>
          <ul className="space-y-1.5 text-sm">
            {hardGates.map((g) => (
              <li key={g.gate_code} className="flex gap-2">
                <span className="mt-0.5 shrink-0 rounded border border-red-600/50 bg-red-950/20 px-1.5 text-xs text-red-300">
                  hard
                </span>
                <span>
                  <span className="font-medium">{g.gate_code}</span>
                  {g.detail ? <span className="text-muted-foreground"> — {g.detail}</span> : null}
                </span>
              </li>
            ))}
            {softGates.map((g) => (
              <li key={g.gate_code} className="flex gap-2 text-muted-foreground">
                <span className="mt-0.5 shrink-0 rounded border border-border px-1.5 text-xs">
                  {g.severity}
                </span>
                <span>
                  <span className="font-medium text-foreground">{g.gate_code}</span>
                  {g.detail ? <span> — {g.detail}</span> : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        {decision.lane_weight_profile === "sub" ? "Sub" : "Prime"} priority formula
        {decision.formula_version ? ` v${decision.formula_version}` : ""}
        {decision.knowledge_pack_version ? ` · pack ${decision.knowledge_pack_version.slice(0, 40)}` : ""}
      </p>
    </section>
  );
}
