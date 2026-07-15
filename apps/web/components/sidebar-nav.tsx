"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  {
    href: "/dashboard",
    label: "Dashboard",
    sub: "Your lane today",
    match: (p: string) => p === "/dashboard"
  },
  {
    href: "/opportunities",
    label: "Opportunities",
    sub: "All scored federal opps",
    match: (p: string) => p.startsWith("/opportunities")
  },
  {
    href: "/pipeline",
    label: "Pipeline",
    sub: "Active pursuits",
    match: (p: string) => p.startsWith("/pipeline")
  },
  {
    href: "/bid-invites",
    label: "Bid Invites",
    sub: "Inbound GC solicitations",
    match: (p: string) => p.startsWith("/bid-invites")
  },
  {
    href: "/library",
    label: "Library",
    sub: "Capability statements",
    match: (p: string) => p.startsWith("/library")
  },
  {
    href: "/drafts",
    label: "Drafts",
    sub: "Sources Sought + RFP",
    match: (p: string) => p.startsWith("/drafts")
  },
  {
    href: "/sbir",
    label: "SBIR Topics",
    sub: "Open DoD SBIR/STTR topics",
    match: (p: string) =>
      p === "/sbir" || (p.startsWith("/sbir") && !p.startsWith("/sbir/submit") && !p.startsWith("/sbir/submissions"))
  },
  {
    href: "/sbir/submit",
    label: "SBIR Submission",
    sub: "Topic → certifiable package",
    match: (p: string) =>
      p.startsWith("/sbir/submit") || p.startsWith("/sbir/submissions")
  },
  {
    href: "/tools/cyber-scope-parser",
    label: "Cyber Scope",
    sub: "FRCS / OT / UFGS feed",
    match: (p: string) => p.startsWith("/tools")
  },
  {
    href: "/forecasts",
    label: "Forecasts",
    sub: "Coming to SAM 30–180d out",
    match: (p: string) => p.startsWith("/forecasts")
  },
  {
    href: "/recompetes",
    label: "Recompetes",
    sub: "Forecasts with named incumbents",
    match: (p: string) => p.startsWith("/recompetes")
  },
  {
    href: "/events",
    label: "Events",
    sub: "Industry days + pre-sol",
    match: (p: string) => p.startsWith("/events")
  },
  {
    href: "/settings",
    label: "Settings",
    sub: "Tenant & founders",
    match: (p: string) => p.startsWith("/settings")
  },
  {
    href: "/onboarding",
    label: "Setup",
    sub: "Tenant identity wizard",
    match: (p: string) => p.startsWith("/onboarding")
  }
];

export function SidebarNav() {
  const pathname = usePathname() ?? "";
  return (
    <nav className="px-3 py-3 space-y-1" aria-label="Primary">
      {NAV.map((item) => {
        const active = item.match(pathname);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={
              active
                ? "block rounded-md border-l-2 border-primary bg-primary/10 px-3 py-2 text-sm text-foreground"
                : "block rounded-md border-l-2 border-transparent px-3 py-2 text-sm text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            }
          >
            <span className="block font-semibold">{item.label}</span>
            <span
              className={
                active
                  ? "block text-xs text-primary"
                  : "block text-xs text-muted-foreground"
              }
            >
              {item.sub}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
