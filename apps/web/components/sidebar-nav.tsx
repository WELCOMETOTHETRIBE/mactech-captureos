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
    href: "/settings",
    label: "Settings",
    sub: "Tenant & founders",
    match: (p: string) => p.startsWith("/settings")
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
                ? "block rounded-md bg-neutral-900 px-3 py-2 text-sm text-white"
                : "block rounded-md px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 hover:text-neutral-900"
            }
          >
            <span className="block font-medium">{item.label}</span>
            <span
              className={
                active
                  ? "block text-[11px] text-neutral-300"
                  : "block text-[11px] text-neutral-500"
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
