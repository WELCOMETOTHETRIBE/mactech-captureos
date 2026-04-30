import { Card, fmtDate } from "@/components/ui";
import type { AuditEventOut, AuditTrailOut } from "@/lib/api";

const EVENT_LABEL: Record<string, string> = {
  "pursuit.created": "Pursuit created",
  "pursuit.stage_changed": "Stage changed",
  "pursuit.owner_changed": "Owner changed",
  "pursuit.notes_updated": "Notes updated",
  "pursuit.win_strategy_updated": "Win strategy updated",
  "pursuit.bid_decided": "Bid decision recorded",
  "pursuit.deleted": "Pursuit deleted",
  "pursuit.past_performance_replaced": "Past performance selection updated",
  "pursuit.key_personnel_replaced": "Key personnel selection updated",
  "pursuit.teaming_partners_replaced": "Teaming partners selection updated",
  "opportunity.amendment_detected": "Opportunity amended",
  "solicitation.extraction_completed": "Solicitation re-extracted",
};

export function AuditTrailCard({ trail }: { trail: AuditTrailOut | null }) {
  if (!trail || trail.events.length === 0) {
    return (
      <Card title="Audit trail">
        <p className="text-sm text-neutral-600">
          No events captured yet. Events appear here when pursuit data
          changes (stage, owner, win strategy, bid decision, asset selection)
          or when SAM.gov detects an amendment.
        </p>
      </Card>
    );
  }
  return (
    <Card title={`Audit trail (${trail.events.length})`}>
      <ol className="space-y-3">
        {trail.events.map((event) => (
          <li
            key={event.id}
            className="border-l-2 border-neutral-200 pl-3 text-sm"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium text-neutral-900">
                {EVENT_LABEL[event.event_type] ?? event.event_type}
              </p>
              <span className="text-[11px] text-neutral-500">
                {fmtDate(event.created_at)}
              </span>
            </div>
            <p className="text-[11px] text-neutral-500">
              {actorLabel(event)}
              <PayloadInline payload={event.payload} eventType={event.event_type} />
            </p>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function actorLabel(event: AuditEventOut): string {
  if (event.actor_user_email) return `by ${event.actor_user_email}`;
  if (event.actor_founder_name) {
    return `by ${event.actor_founder_name} (@${event.actor_founder_slug})`;
  }
  if (event.actor_label) return `by ${event.actor_label}`;
  return "by system";
}

function PayloadInline({
  payload,
  eventType,
}: {
  payload: Record<string, unknown>;
  eventType: string;
}) {
  if (!payload || Object.keys(payload).length === 0) return null;

  if (eventType === "pursuit.stage_changed") {
    return (
      <span>
        {" · "}
        {String(payload.from)} → {String(payload.to)}
      </span>
    );
  }
  if (eventType === "pursuit.bid_decided") {
    return (
      <span>
        {" · "}
        {payload.from ? `${payload.from} → ` : ""}
        {String(payload.to ?? payload.decision ?? "")}
      </span>
    );
  }
  if (
    eventType === "pursuit.past_performance_replaced" ||
    eventType === "pursuit.key_personnel_replaced" ||
    eventType === "pursuit.teaming_partners_replaced"
  ) {
    return (
      <span>
        {" · "}
        {String(payload.selection_count ?? 0)} item
        {payload.selection_count === 1 ? "" : "s"} selected
      </span>
    );
  }
  if (eventType === "opportunity.amendment_detected") {
    const fields = payload.fields_changed;
    if (Array.isArray(fields) && fields.length > 0) {
      return (
        <span>
          {" · "}fields: {fields.join(", ")}
        </span>
      );
    }
  }
  if (eventType === "pursuit.win_strategy_updated") {
    return (
      <span>
        {" · "}
        {String(payload.win_theme_count ?? 0)} themes /{" "}
        {String(payload.discriminator_count ?? 0)} discriminators
      </span>
    );
  }
  return null;
}
