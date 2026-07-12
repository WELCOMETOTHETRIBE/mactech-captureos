"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type State =
  | { kind: "idle" }
  | { kind: "pulling" }
  | { kind: "done"; fetched: number; upserted: number; detailsOk: number; elapsed: number }
  | { kind: "error"; message: string };

export function SBIRTopicsRefreshButton() {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "idle" });

  async function refresh() {
    setState({ kind: "pulling" });
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
      fetched: number;
      upserted: number;
      details_ok: number;
      elapsed_secs: number;
      error: string | null;
    };
    if (body.error) {
      setState({ kind: "error", message: body.error });
      return;
    }
    setState({
      kind: "done",
      fetched: body.fetched,
      upserted: body.upserted,
      detailsOk: body.details_ok,
      elapsed: body.elapsed_secs
    });
    router.refresh();
  }

  return (
    <div className="flex flex-col items-end gap-1 text-right">
      <button
        type="button"
        onClick={refresh}
        disabled={state.kind === "pulling"}
        className="rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:border-foreground/30 disabled:opacity-50"
      >
        {state.kind === "pulling" ? "Pulling from DSIP…" : "Refresh feed"}
      </button>
      {state.kind === "pulling" && (
        <span className="text-[11px] text-muted-foreground">
          Pulling full topic content · ~30–60s
        </span>
      )}
      {state.kind === "done" && (
        <span className="text-[11px] text-muted-foreground">
          {state.upserted} topics · {state.detailsOk} with full detail ·{" "}
          {state.elapsed.toFixed(0)}s
        </span>
      )}
      {state.kind === "error" && (
        <span className="text-[11px] text-destructive">{state.message}</span>
      )}
    </div>
  );
}
