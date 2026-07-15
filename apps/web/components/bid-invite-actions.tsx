"use client";

import { useFormStatus } from "react-dom";
import { Button } from "@/components/ui";

/**
 * Pending-aware triage buttons for bid invites. Server actions arrive
 * pre-bound from the page (same idiom as cyber-scope-action-buttons):
 * each button is its own <form action> so useFormStatus scopes the
 * "working…" state to the clicked control only.
 */

function PendingButton({
  children,
  variant = "secondary"
}: {
  children: React.ReactNode;
  variant?: "secondary" | "ghost" | "danger";
}) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="xs" variant={variant} disabled={pending}>
      {pending ? "Working…" : children}
    </Button>
  );
}

export function BidInviteAction({
  action,
  label,
  variant = "secondary"
}: {
  action: () => Promise<void>;
  label: string;
  variant?: "secondary" | "ghost" | "danger";
}) {
  return (
    <form action={action} className="inline-flex">
      <PendingButton variant={variant}>{label}</PendingButton>
    </form>
  );
}
