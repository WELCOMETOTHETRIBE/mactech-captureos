import { UserButton } from "@clerk/nextjs";
import { apiFetch, type MeResponse } from "@/lib/api";
import { SidebarNav } from "@/components/sidebar-nav";
import { CmdK, CmdKTrigger } from "@/components/cmd-k";
import { MacTechFooter } from "@/components/footer";
import { Pillar } from "@/components/ui";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  let me: MeResponse | null = null;
  try {
    me = await apiFetch<MeResponse>("/me");
  } catch (err) {
    // Render the shell even if /me fails so users see an error state instead of a blank screen.
    console.error("Failed to load /me", err);
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper-50">
      <div className="grid flex-1 grid-cols-[240px_1fr]">
      <aside className="flex flex-col border-r border-paper-200 bg-white">
        <div className="px-5 py-5 border-b border-neutral-200">
          <p className="text-[10px] uppercase tracking-wider text-neutral-500">
            {me?.tenant.name ?? "MacTech"}
          </p>
          <p className="text-base font-semibold tracking-tight text-neutral-900">
            CaptureOS
          </p>
          <p className="mt-1 text-[10px] text-neutral-400">
            The operating system for defense contractors.
          </p>
        </div>

        {/* Cmd-K trigger — keyboard works anywhere; this button is the
            discoverable affordance for users who haven't learned the
            shortcut yet. */}
        <div className="px-3 pt-3">
          <CmdKTrigger />
        </div>

        <SidebarNav />

        <div className="mt-auto border-t border-neutral-200 px-5 py-4 text-xs">
          {me?.founder ? (
            <>
              <p className="font-medium text-neutral-800">
                {me.founder.full_name}
              </p>
              <p className="text-neutral-500">{me.founder.title}</p>
              <div className="mt-2">
                <Pillar pillar={me.founder.pillar} />
              </div>
            </>
          ) : me ? (
            <>
              <p className="font-medium text-neutral-800">{me.user_email}</p>
              <p className="mt-1 text-neutral-500">
                Tenant member — not yet linked to a founder profile.
              </p>
            </>
          ) : (
            <p className="text-neutral-500">Loading session…</p>
          )}
        </div>
      </aside>

      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-6 py-3">
          <div className="flex items-center gap-3 text-sm text-neutral-600">
            {me?.tenant ? (
              <>
                <span className="font-medium text-neutral-800">
                  {me.tenant.name}
                </span>
                <span className="text-neutral-300">·</span>
                <span className="text-xs uppercase tracking-wider text-neutral-500">
                  {me.tenant.plan}
                </span>
              </>
            ) : (
              <span>—</span>
            )}
          </div>
          <UserButton afterSignOutUrl="/" />
        </header>
        <main className="flex-1 px-6 py-6">{children}</main>
      </div>

      </div>
      <MacTechFooter />

      {/* Global Cmd-K modal — single mount, listens for the shortcut
          anywhere in the app. */}
      <CmdK />
    </div>
  );
}
