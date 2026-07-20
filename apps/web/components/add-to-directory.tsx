"use client";

import { useActionState } from "react";
import type { AddInviteContactResult } from "@/lib/api";

export type AddToDirectoryState = {
  outcome: AddInviteContactResult["outcome"] | "error" | null;
  message?: string;
};

/**
 * One-click "Add to Directory" for contacts parsed out of ingested mail.
 * Deliberately explicit (no auto-sync): not every GC lead belongs in the
 * company address book. The action is idempotent server-side, so the
 * "already in directory" outcome is a normal state, not an error.
 */
export function AddToDirectoryButton({
  action
}: {
  action: (prev: AddToDirectoryState) => Promise<AddToDirectoryState>;
}) {
  const [state, formAction, pending] = useActionState<AddToDirectoryState>(action, {
    outcome: null
  });

  if (state.outcome === "added" || state.outcome === "exists") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
        ✓ {state.outcome === "added" ? "Added to Directory" : "Already in Directory"}
      </span>
    );
  }

  return (
    <form action={formAction} className="inline-flex flex-col gap-1">
      <button
        type="submit"
        disabled={pending}
        className="inline-flex w-fit items-center rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-60"
      >
        {pending ? "Adding…" : "+ Add to Directory"}
      </button>
      {state.outcome === "error" && (
        <span className="text-xs text-destructive">{state.message ?? "Failed — try again."}</span>
      )}
    </form>
  );
}
