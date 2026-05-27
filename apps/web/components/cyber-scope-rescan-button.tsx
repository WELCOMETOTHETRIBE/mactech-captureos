"use client";

import { useFormStatus } from "react-dom";
import { rescanOpportunityCyberScope } from "@/lib/cyber-scope";
import { Button } from "@/components/ui";

function SubmitBtn() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" variant="secondary" disabled={pending}>
      {pending ? "Re-scanning…" : "Re-run cyber scope"}
    </Button>
  );
}

export function CyberScopeRescanButton({
  opportunityId,
}: {
  opportunityId: string;
}) {
  async function action() {
    "use server";
    await rescanOpportunityCyberScope(opportunityId);
  }

  return (
    <form action={action}>
      <SubmitBtn />
    </form>
  );
}
