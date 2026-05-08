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
  /** Title accepts a string or any inline node so we can wrap terms with
   * ``<Term>``/``<ExplainLink>`` (e.g. "Compliance matrix · Section L"). */
  title?: ReactNode;
  children: ReactNode;
  className?: string;
  trailing?: ReactNode;
}) {
  // Hairline border, no shadow at rest. White card on warm-paper page bg
  // gives just enough lift without the "every section is a card" noise.
  // Token-driven so the same primitive re-skins across MacTech apps.
  return (
    <section
      className={`rounded-md border border-border bg-card p-6 ${className}`}
    >
      {title && (
        <header className="flex items-center justify-between">
          <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {title}
          </h2>
          {trailing}
        </header>
      )}
      {title ? <div className="mt-4">{children}</div> : children}
    </section>
  );
}

/**
 * Soft section — borderless content block, only spacing + an optional
 * label. Use this instead of Card when the content doesn't need a
 * visible frame (e.g., the hero strip on a detail page, or a list of
 * items inside a parent Card). Reduces the "every block is a card"
 * noise that's been creeping in.
 */
export function Section({
  title,
  trailing,
  children,
  className = ""
}: {
  title?: ReactNode;
  trailing?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={className}>
      {title && (
        <header className="flex items-center justify-between border-b border-border pb-2">
          <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {title}
          </h2>
          {trailing}
        </header>
      )}
      <div className={title ? "mt-3" : ""}>{children}</div>
    </section>
  );
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  trailing,
  display = false,
  size = "default"
}: {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  trailing?: ReactNode;
  /** When true, render the title as italic serif — used for editorial /
   * decision-oriented surfaces (opportunity, pursuit, capture package).
   * Default false keeps the existing sans treatment for utility pages
   * (settings, library admin, drafts list). */
  display?: boolean;
  /** "sm" tightens the title for conversational headers (the dashboard
   * greeting). "default" is the standard 3xl treatment used on every
   * other top-level page. */
  size?: "default" | "sm";
}) {
  let titleClass: string;
  if (display) {
    titleClass =
      size === "sm"
        ? "mt-1 text-2xl font-medium italic tracking-tight text-foreground font-serif leading-tight"
        : "mt-1 text-4xl font-medium italic tracking-tight text-foreground font-serif leading-tight";
  } else {
    titleClass =
      size === "sm"
        ? "mt-1 text-xl font-semibold tracking-tight text-foreground"
        : "mt-1 text-3xl font-semibold tracking-tight text-foreground";
  }
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 flex-1">
        {eyebrow && (
          <p className="text-xs font-medium uppercase tracking-wide text-primary">
            {eyebrow}
          </p>
        )}
        <h1 className={titleClass}>{title}</h1>
        {subtitle && (
          <div className={`${size === "sm" ? "mt-1" : "mt-2"} text-sm text-muted-foreground`}>
            {subtitle}
          </div>
        )}
      </div>
      {trailing && <div className="shrink-0">{trailing}</div>}
    </header>
  );
}

export function Kpi({
  label,
  value,
  hint,
  tone = "neutral"
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "neutral" | "brand" | "amber" | "red";
}) {
  // Tone names stay back-compat for existing callers, but map to the
  // semantic token contract underneath: amber→warning, red→destructive,
  // brand→primary. This is the §7.7 leverage point — same API, themable
  // values.
  const valueTones: Record<string, string> = {
    neutral: "text-foreground",
    brand: "text-primary",
    amber: "text-warning",
    red: "text-destructive"
  };
  return (
    <div className="rounded-md border border-border bg-card p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p
        className={`mt-2 text-3xl font-semibold tabular-nums ${valueTones[tone]}`}
      >
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function Badge({
  tone = "neutral",
  children,
  title
}: {
  tone?: "neutral" | "blue" | "green" | "amber" | "red" | "violet" | "brand";
  children: ReactNode;
  title?: string;
}) {
  // tone names remain back-compat for existing callers; map to semantic
  // tokens where possible. blue/violet stay on raw Tailwind palettes
  // because they carry pillar / informational meaning that we'll promote
  // into pillar tokens in a follow-up pass (the chip layout is right; the
  // color values are a future-pass concern).
  const tones: Record<string, string> = {
    neutral: "bg-muted text-muted-foreground border-border",
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    green: "bg-success/10 text-success border-success/20",
    amber: "bg-warning/10 text-warning border-warning/20",
    red: "bg-destructive/10 text-destructive border-destructive/20",
    violet: "bg-violet-50 text-violet-700 border-violet-100",
    brand: "bg-primary/10 text-primary border-primary/20"
  };
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${tones[tone]}${
        title ? " cursor-help" : ""
      }`}
    >
      {children}
    </span>
  );
}

export function ScoreBadge({
  score,
  size = "default"
}: {
  score: number | null;
  size?: "default" | "lg";
}) {
  if (score == null) {
    return <Badge tone="neutral">—</Badge>;
  }
  const tone =
    score >= 80 ? "brand" : score >= 60 ? "blue" : score >= 40 ? "amber" : "neutral";
  const label =
    score >= 80
      ? "Strong fit — pursue"
      : score >= 60
      ? "Worth a look"
      : score >= 40
      ? "Watch list"
      : "Long shot";
  if (size === "lg") {
    const tones: Record<string, string> = {
      brand: "bg-primary/10 text-primary border-primary/20",
      blue: "bg-blue-50 text-blue-800 border-blue-200",
      amber: "bg-warning/10 text-warning border-warning/20",
      neutral: "bg-muted text-muted-foreground border-border"
    };
    return (
      <span
        title={`${label}. Scores: ≥80 strong fit, 60–79 worth a look, 40–59 watch list, <40 long shot.`}
        className={`inline-flex items-baseline gap-1 rounded-md border px-2.5 py-1 ${tones[tone]} cursor-help`}
      >
        <span className="text-base font-semibold tabular-nums">{score}</span>
        <span className="text-[10px] uppercase tracking-wide">/ 100</span>
      </span>
    );
  }
  return (
    <Badge tone={tone} title={`${label}. Score ${score} of 100.`}>
      <span className="tabular-nums">{score}</span>
    </Badge>
  );
}

/**
 * Single-button primitive. Use this for actions; LinkButton is for navigation.
 * `primary` is the brand-teal CTA, used at most once per surface.
 */
export function Button({
  children,
  variant = "secondary",
  type = "button",
  className = "",
  ...rest
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  type?: "button" | "submit" | "reset";
  className?: string;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "type" | "className">) {
  const variants: Record<string, string> = {
    primary:
      "border border-primary bg-primary text-primary-foreground hover:bg-primary/90 hover:border-primary",
    secondary:
      "border border-input bg-card text-foreground hover:bg-accent hover:text-accent-foreground",
    ghost:
      "border border-transparent text-foreground hover:bg-accent hover:text-accent-foreground",
    danger:
      "border border-destructive/40 bg-card text-destructive hover:bg-destructive/10 hover:border-destructive"
  };
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center rounded-md px-3.5 py-2 text-sm font-medium transition-colors ${variants[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
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
    <div className="rounded-md border border-dashed border-border bg-card px-6 py-12 text-center">
      <p className="text-sm font-medium text-foreground">{title}</p>
      {body && <p className="mt-1 text-sm text-muted-foreground">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Pillar({ pillar }: { pillar: string }) {
  // Pillar tones are first-class tokens (--pillar-security / -infrastructure
  // / -quality / -governance) so the next MacTech app reuses them
  // unchanged. The chip is a soft tint (color/15 background, color/90
  // text, color/20 border) — same shape as the other Badge tones.
  const classes: Record<string, string> = {
    security:
      "bg-pillar-security/15 text-pillar-security border-pillar-security/20",
    infrastructure:
      "bg-pillar-infrastructure/15 text-pillar-infrastructure border-pillar-infrastructure/20",
    quality:
      "bg-pillar-quality/15 text-pillar-quality border-pillar-quality/20",
    governance:
      "bg-pillar-governance/15 text-pillar-governance border-pillar-governance/20"
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
  const cls = classes[pillar];
  if (!cls) {
    return (
      <Badge tone="neutral" title={help[pillar]}>
        {pillar}
      </Badge>
    );
  }
  return (
    <span
      title={help[pillar]}
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${cls}${
        help[pillar] ? " cursor-help" : ""
      }`}
    >
      {pillar}
    </span>
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

/**
 * Wraps any badge or chip in a hyperlink that opens the "Explain this"
 * right rail with the given term slug. Use only on pages that render
 * the rail (currently /opportunities/[id]).
 *
 * Slug format: <kind>:<value> — e.g. "naics:541512", "set_aside:SDVOSB".
 * Relative href (`?explain=...`) preserves the current path and other
 * search params; the browser resolves it against the current URL.
 */
export function ExplainLink({
  slug,
  children,
  className = ""
}: {
  slug: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Link
      href={`?explain=${encodeURIComponent(slug)}`}
      scroll={false}
      className={`inline-flex items-center rounded-md transition-colors hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${className}`}
      aria-label="Explain this term in plain English"
      title="Click for a plain-English explanation"
    >
      {children}
      <span aria-hidden className="ml-1 text-[10px] text-brand-700">?</span>
    </Link>
  );
}

/**
 * Term — sugar over ExplainLink for inline jargon. Renders the term
 * inline (no surrounding badge) with a small ? affordance. Use when
 * the term IS the content (e.g., "FAR 52.204-21" inside a sentence,
 * or "Section L" as a column header). For badge-shaped chips, wrap
 * the existing badge in <ExplainLink slug=...> instead.
 *
 * Slug format mirrors the explain backend: kind:value. Common kinds:
 *   - clause      e.g. clause:FAR 52.204-21 / clause:DFARS 252.204-7012
 *   - cmmc        e.g. cmmc:Level 2
 *   - section     e.g. section:L / section:M / section:SOW
 *   - sprs        e.g. sprs:score
 *   - cui / fci / itar
 *   - uei / cage / fcl
 *   - naics       e.g. naics:541512
 *   - set_aside_cert  e.g. set_aside_cert:SDVOSB
 */
export function Term({
  kind,
  value,
  children,
  className = ""
}: {
  kind: string;
  value: string;
  /** Optional override for what's displayed. Defaults to ``value``. */
  children?: ReactNode;
  className?: string;
}) {
  const slug = `${kind}:${value}`;
  return (
    <ExplainLink slug={slug} className={className}>
      <span className="border-b border-dotted border-brand-300/70">
        {children ?? value}
      </span>
    </ExplainLink>
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
        title="Service-Disabled Veteran-Owned Small Business set-aside. MacTech is SDVOSB-certified."
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
  variant?: "primary" | "secondary" | "ghost";
  external?: boolean;
}) {
  const variants: Record<string, string> = {
    primary:
      "border border-primary bg-primary text-primary-foreground hover:bg-primary/90 hover:border-primary",
    secondary:
      "border border-input bg-card text-foreground hover:bg-accent hover:text-accent-foreground",
    ghost: "border border-transparent text-foreground hover:bg-accent hover:text-accent-foreground"
  };
  const cls = `inline-flex items-center justify-center rounded-md px-3.5 py-2 text-sm font-medium transition-colors ${variants[variant]}`;
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
