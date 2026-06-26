"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type State =
  | { kind: "idle" }
  | { kind: "kicking" }
  | { kind: "queued"; taskId: string }
  | { kind: "noop"; detail: string }
  | { kind: "error"; message: string };

export function SBIRTopicsRefreshButton() {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "idle" });

  async function refresh() {
    setState({ kind: "kicking" });
    let res: Response;
    try {
      res = await fetch("/sbir/topics-refresh", { method: "POST" });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "network error"
      });
      return;
    }
    if (!res.ok) {
      let detail = `request failed (${res.status})`;
      try {
        const j = (await res.json()) as { error?: string; detail?: string };
        if (j.error) detail = j.error;
        else if (j.detail) detail = j.detail;
      } catch {
        // ignore
      }
      setState({ kind: "error", message: detail });
      return;
    }
    const body = (await res.json()) as {
      queued: boolean;
      task_id: string | null;
      detail: string | null;
    };
    if (body.queued && body.task_id) {
      setState({ kind: "queued", taskId: body.task_id });
      router.refresh();
    } else {
      setState({
        kind: "noop",
        detail: body.detail ?? "broker unavailable"
      });
    }
  }

  return (
    <div className="flex flex-col items-end gap-1 text-right">
      <button
        type="button"
        onClick={refresh}
        disabled={state.kind === "kicking"}
        className="rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:border-foreground/30 disabled:opacity-50"
      >
        {state.kind === "kicking" ? "Queuing…" : "Refresh feed"}
      </button>
      {state.kind === "queued" && (
        <span className="text-[11px] text-muted-foreground">
          Queued · run takes 5–10 min
        </span>
      )}
      {state.kind === "noop" && (
        <span className="text-[11px] text-warning">{state.detail}</span>
      )}
      {state.kind === "error" && (
        <span className="text-[11px] text-destructive">{state.message}</span>
      )}
    </div>
  );
}
