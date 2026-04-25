import Link from "next/link";
import { UserButton } from "@clerk/nextjs";
import { apiFetch, type MeResponse } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/opportunities", label: "Opportunities" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/library", label: "Library" },
  { href: "/settings", label: "Settings" }
];

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  let me: MeResponse | null = null;
  try {
    me = await apiFetch<MeResponse>("/me");
  } catch (err) {
    // Render the shell even if /me fails so users see an error state instead of a blank screen.
    console.error("Failed to load /me", err);
  }

  return (
    <div className="grid min-h-screen grid-cols-[220px_1fr] bg-neutral-50">
      <aside className="border-r border-neutral-200 bg-white">
        <div className="px-5 py-5 border-b border-neutral-200">
          <p className="text-[10px] uppercase tracking-wider text-neutral-500">MacTech</p>
          <p className="text-sm font-semibold text-neutral-900">CaptureOS</p>
        </div>
        <nav className="px-3 py-4 space-y-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-md px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 hover:text-neutral-900"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        {me?.founder && (
          <div className="px-5 py-4 mt-4 border-t border-neutral-200 text-xs text-neutral-500">
            <p className="font-medium text-neutral-700">{me.founder.full_name}</p>
            <p>{me.founder.title}</p>
            <p className="mt-1 capitalize">{me.founder.pillar} pillar</p>
          </div>
        )}
      </aside>

      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-6 py-3">
          <div className="text-sm text-neutral-500">
            {me?.tenant ? <span>{me.tenant.name}</span> : <span>—</span>}
          </div>
          <UserButton afterSignOutUrl="/" />
        </header>
        <main className="flex-1 px-6 py-6">{children}</main>
      </div>
    </div>
  );
}
