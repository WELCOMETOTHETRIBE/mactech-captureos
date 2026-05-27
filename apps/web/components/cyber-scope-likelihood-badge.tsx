import { Badge } from "@/components/ui";

const LIKELIHOOD_TONE: Record<
  string,
  "neutral" | "green" | "amber" | "red" | "violet"
> = {
  NONE: "neutral",
  LOW: "neutral",
  MEDIUM: "amber",
  HIGH: "red",
  CRITICAL: "violet",
};

export function CyberScopeLikelihoodBadge({
  likelihood,
}: {
  likelihood: string;
}) {
  const tone = LIKELIHOOD_TONE[likelihood] ?? "neutral";
  return <Badge tone={tone}>{likelihood}</Badge>;
}

export function PursuitModelBadge({ model }: { model: string }) {
  const label = model.replace(/_/g, " ");
  return (
    <Badge tone="blue" title={model}>
      {label}
    </Badge>
  );
}
