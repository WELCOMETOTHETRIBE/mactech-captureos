"use client";

import { useFormStatus } from "react-dom";
import { Button } from "@/components/ui";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending}>
      {pending ? "Analyzing…" : "Analyze off-platform text"}
    </Button>
  );
}

export function CyberScopeOffplatformForm({
  action,
}: {
  action: (formData: FormData) => Promise<void>;
}) {
  return (
    <form action={action} className="space-y-3">
      <label className="block text-sm">
        <span className="text-muted-foreground">Opportunity title (optional)</span>
        <input
          name="title"
          type="text"
          className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        />
      </label>
      <label className="block text-sm">
        <span className="text-muted-foreground">
          Paste solicitation / spec excerpt (prime package, email, etc.)
        </span>
        <textarea
          name="text"
          required
          rows={6}
          className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
          placeholder="UFGS 25 05 11, BACnet DDC, RMF ATO…"
        />
      </label>
      <SubmitButton />
    </form>
  );
}
