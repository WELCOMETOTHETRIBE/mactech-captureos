import type { OpportunityDetail } from "@/lib/api";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const CONFIDENCE_CLASS: Record<string, string> = {
  confirmed: "text-emerald-300",
  probable: "text-emerald-300",
  possible: "text-amber-300",
  unknown: "text-muted-foreground",
};

export function PursuitPlanPanel({
  plan,
  primeTargets,
}: {
  plan: OpportunityDetail["pursuit_plan"];
  primeTargets: OpportunityDetail["prime_targets"];
}) {
  if (!plan && primeTargets.length === 0) return null;

  return (
    <section className="rounded-md border border-border bg-card p-5 space-y-5">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Pursuit plan
      </h3>

      {plan && (
        <div className="space-y-3">
          <p className="text-sm font-medium">{plan.executive_decision}</p>
          {plan.mactech_work_package && (
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                MacTech work package
              </div>
              <p className="text-sm text-foreground/90">{plan.mactech_work_package}</p>
            </div>
          )}
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
            {plan.decision_deadline && (
              <span>
                Decide by{" "}
                <span className="font-medium text-foreground">
                  {fmtDate(plan.decision_deadline)}
                </span>
              </span>
            )}
            {plan.recommended_owner_slug && (
              <span>
                Lead <span className="font-medium text-foreground">@{plan.recommended_owner_slug}</span>
              </span>
            )}
          </div>
        </div>
      )}

      {primeTargets.length > 0 && (
        <div className="space-y-2 border-t border-border pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Target primes (USASpending award history)
          </h4>
          <ol className="space-y-2 text-sm">
            {primeTargets.slice(0, 5).map((pt) => (
              <li key={`${pt.rank}-${pt.name}`} className="flex gap-2">
                <span className="tabular-nums text-muted-foreground">{pt.rank + 1}.</span>
                <span>
                  <span className="font-medium">{pt.name}</span>{" "}
                  <span className={`text-xs ${CONFIDENCE_CLASS[pt.confidence] ?? ""}`}>
                    [{pt.confidence}]
                  </span>
                  {pt.why_target && (
                    <span className="block text-xs text-muted-foreground">{pt.why_target}</span>
                  )}
                  {pt.recommended_contact_role && (
                    <span className="block text-xs text-muted-foreground">
                      contact: {pt.recommended_contact_role}
                      {pt.outreach_deadline ? ` · by ${fmtDate(pt.outreach_deadline)}` : ""}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {plan && plan.actions.length > 0 && (
        <div className="space-y-2 border-t border-border pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Next actions
          </h4>
          <ol className="space-y-1.5 text-sm">
            {plan.actions.map((a) => (
              <li key={a.sequence} className="flex gap-2">
                <span className="tabular-nums text-muted-foreground">{a.sequence}.</span>
                <span>
                  <span className="text-foreground">{a.action}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {a.owner_founder_slug ? `@${a.owner_founder_slug}` : ""}
                    {a.due_at ? ` · by ${fmtDate(a.due_at)}` : ""}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
