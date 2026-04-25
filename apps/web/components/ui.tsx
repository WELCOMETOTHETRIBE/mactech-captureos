import type { ReactNode } from "react";
import Link from "next/link";

/**
 * Small UI primitives shared across pages. Tailwind-only, no client JS,
 * no third-party deps. Goal is consistent visual rhythm.
 */

export function Card({
  title,
  children,
  className = "",
  trailing
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  trailing?: ReactNode;
}) {
  return (
    <section
      className={`rounded-md border border-neutral-200 bg-white p-5 ${className}`}
    >
      {title && (
        <header className="flex items-center justify-between">
          <h2 className="text-[11px] uppercase tracking-wider text-neutral-500">
            {title}
          </h2>
          {trailing}
        </header>
      )}
      {title ? <div className="mt-3">{children}</div> : children}
    </section>
  );
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  trailing
}: {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  trailing?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        {eyebrow && (
          <p className="text-xs uppercase tracking-wider text-neutral-500">
            {eyebrow}
          </p>
        )}
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-neutral-900">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 text-sm text-neutral-600">{subtitle}</p>
        )}
      </div>
      {trailing && <div className="shrink-0">{trailing}</div>}
    </header>
  );
}

export function Kpi({
  label,
  value,
  hint
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-neutral-200 bg-white p-4">
      <p className="text-[11px] uppercase tracking-wider text-neutral-500">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-neutral-900">
        {value}
      </p>
      {hint && <p className="mt-1 text-[11px] text-neutral-500">{hint}</p>}
    </div>
  );
}

export function Badge({
  tone = "neutral",
  children,
  title
}: {
  tone?: "neutral" | "blue" | "green" | "amber" | "red" | "violet";
  children: ReactNode;
  title?: string;
}) {
  const tones: Record<string, string> = {
    neutral: "bg-neutral-100 text-neutral-700 border-neutral-200",
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    green: "bg-emerald-50 text-emerald-700 border-emerald-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
    red: "bg-red-50 text-red-700 border-red-100",
    violet: "bg-violet-50 text-violet-700 border-violet-100"
  };
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}${
        title ? " cursor-help" : ""
      }`}
    >
      {children}
    </span>
  );
}

export function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) {
    return <Badge tone="neutral">—</Badge>;
  }
  const tone =
    score >= 80 ? "green" : score >= 60 ? "blue" : score >= 40 ? "amber" : "neutral";
  return (
    <Badge tone={tone}>
      <span className="tabular-nums">{score}</span>
    </Badge>
  );
}

export function EmptyState({
  title,
  body,
  action
}: {
  title: string;
  body?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-md border border-dashed border-neutral-300 bg-white px-6 py-12 text-center">
      <p className="text-sm font-medium text-neutral-900">{title}</p>
      {body && <p className="mt-1 text-sm text-neutral-600">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Pillar({ pillar }: { pillar: string }) {
  const tones: Record<string, "blue" | "green" | "amber" | "violet"> = {
    security: "blue",
    infrastructure: "green",
    quality: "amber",
    governance: "violet"
  };
  const help: Record<string, string> = {
    security:
      "Security pillar (Patrick Caruso): RMF, ATO, ConMon, STIG, CMMC 2.0 L2, NIST CSF 2.0, FedRAMP Moderate.",
    infrastructure:
      "Infrastructure pillar (James Adams): data center architecture, virtualization, cloud, storage, network, IaC.",
    quality:
      "Quality pillar (Brian MacDonald): ISO 9001/17025, audit readiness, metrology, process documentation.",
    governance:
      "Governance pillar (John Milso): commercial contracts, corporate governance, M&A diligence, risk."
  };
  return (
    <Badge tone={tones[pillar] ?? "neutral"} title={help[pillar]}>
      {pillar}
    </Badge>
  );
}

export function NaicsBadge({ code }: { code: string | null | undefined }) {
  if (!code) return null;
  return (
    <Badge
      tone="neutral"
      title="NAICS = North American Industry Classification System. The federal contracting taxonomy that determines small-business size standards and pursuit fit."
    >
      NAICS {code}
    </Badge>
  );
}

export function SetAsideBadge({ code }: { code: string | null }) {
  if (!code)
    return (
      <Badge
        tone="neutral"
        title="Unrestricted: any qualified business may compete. No socioeconomic preference."
      >
        unrestricted
      </Badge>
    );
  const upper = code.toUpperCase();
  if (upper.startsWith("SDVOSB") || upper === "VSA" || upper === "VSS") {
    return (
      <Badge
        tone="violet"
        title="Service-Disabled Veteran-Owned Small Business set-aside. MacTech's pending SDVOSB status applies here."
      >
        {upper}
      </Badge>
    );
  }
  if (["SBA", "SBP", "SB"].includes(upper))
    return (
      <Badge
        tone="green"
        title="Small Business set-aside. Restricted to SBA-certified small businesses by NAICS size standard."
      >
        {upper}
      </Badge>
    );
  if (upper === "NONE")
    return (
      <Badge
        tone="neutral"
        title="No set-aside designation; full-and-open competition."
      >
        unrestricted
      </Badge>
    );
  if (upper === "8A" || upper.startsWith("8(A)"))
    return (
      <Badge
        tone="violet"
        title="SBA 8(a) Business Development program set-aside. Restricted to certified 8(a) firms."
      >
        {upper}
      </Badge>
    );
  if (upper.startsWith("HUBZONE") || upper === "HZC")
    return (
      <Badge
        tone="green"
        title="HUBZone set-aside: businesses in Historically Underutilized Business Zones."
      >
        {upper}
      </Badge>
    );
  if (upper.startsWith("WOSB") || upper.startsWith("EDWOSB"))
    return (
      <Badge
        tone="green"
        title="Women-Owned Small Business set-aside (or Economically Disadvantaged WOSB)."
      >
        {upper}
      </Badge>
    );
  return (
    <Badge tone="neutral" title={`Set-aside code: ${upper}`}>
      {upper}
    </Badge>
  );
}

export function fmtMoney(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n.toFixed(0)}`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  });
}

export function fmtRelativeDays(iso: string | null, days: number | null | undefined): string {
  if (!iso) return "no deadline";
  const d = fmtDate(iso);
  if (days == null) return d;
  if (days < 0) return `${d} (passed ${-days}d ago)`;
  if (days === 0) return `${d} (today)`;
  if (days === 1) return `${d} (1 day left)`;
  if (days <= 7) return `${d} (${days} days left)`;
  return `${d} (${days}d)`;
}

export function NoticeTypeBadge({ type }: { type: string | null }) {
  if (!type) return <Badge tone="neutral">unknown</Badge>;
  const t = type.toLowerCase();
  if (t.includes("sources sought"))
    return (
      <Badge
        tone="amber"
        title="Market research request. The agency wants capability statements before issuing a real RFP. Often the best leverage point — early."
      >
        sources sought
      </Badge>
    );
  if (t.includes("award"))
    return (
      <Badge tone="green" title="Contract was awarded. Useful for incumbent intelligence on follow-on cycles.">
        award
      </Badge>
    );
  if (t.includes("solicitation") && t.includes("synopsis"))
    return (
      <Badge
        tone="blue"
        title="Combined synopsis/solicitation: the formal RFP is on the table. Proposals are due."
      >
        combined synopsis
      </Badge>
    );
  if (t.includes("solicitation"))
    return (
      <Badge tone="blue" title="Formal RFP / solicitation issued. Bidding window is open.">
        solicitation
      </Badge>
    );
  if (t.includes("presolicitation"))
    return (
      <Badge tone="blue" title="Heads-up: an RFP is coming on this requirement. Position now.">
        presolicitation
      </Badge>
    );
  if (t.includes("special"))
    return (
      <Badge
        tone="neutral"
        title="Special notice — agency announcement that doesn't fit standard categories."
      >
        special notice
      </Badge>
    );
  if (t.includes("justification"))
    return (
      <Badge
        tone="neutral"
        title="Justification & Approval — sole-source award rationale. Generally too late to compete on this one but useful market signal."
      >
        justification
      </Badge>
    );
  return <Badge tone="neutral">{type}</Badge>;
}

export function LinkButton({
  href,
  children,
  variant = "secondary",
  external = false
}: {
  href: string;
  children: ReactNode;
  variant?: "primary" | "secondary";
  external?: boolean;
}) {
  const cls =
    variant === "primary"
      ? "rounded-md border border-neutral-900 bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-800"
      : "rounded-md border border-neutral-300 px-3 py-2 text-sm text-neutral-800 hover:border-neutral-500";
  if (external) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={cls}>
        {children}
      </a>
    );
  }
  return (
    <Link href={href} className={cls}>
      {children}
    </Link>
  );
}
