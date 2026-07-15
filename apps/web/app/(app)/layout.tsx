import { UserButton } from "@clerk/nextjs";
import { apiFetch, type MeResponse } from "@/lib/api";
import { SidebarNav } from "@/components/sidebar-nav";
import { CmdK, CmdKTrigger } from "@/components/cmd-k";
import { KeyboardShortcuts } from "@/components/keyboard-shortcuts";
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
    <div className="min-h-screen flex flex-col bg-background">
      <div className="grid flex-1 grid-cols-[240px_1fr]">
      <aside className="flex flex-col border-r border-border bg-card">
        <div className="px-5 py-5 border-b border-border">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {me?.tenant.name ?? "MacTech"}
          </p>
          <p className="text-base font-semibold tracking-tight text-foreground">
            CaptureOS
          </p>
          <p className="mt-1 text-[10px] text-muted-foreground">
            The operating system for defense contractors.
          </p>
        </div>

        {/* Cmd-K trigger — keyboard works anywhere; this button is the
            discoverable affordance for users who haven't learned the
            shortcut yet. */}
        <div className="px-3 pt-3">
          <CmdKTrigger />
        </div>

        <SidebarNav bidInvitesUnseen={me?.bid_invites_unseen ?? 0} />

        {/* Keyboard shortcuts hint — discoverable affordance for the
            global ? help modal. Static label, the modal opens via the
            global keypress listener in <KeyboardShortcuts />. */}
        <div className="px-5 pb-3">
          <p className="text-[10px] text-muted-foreground">
            Press{" "}
            <kbd className="rounded border border-border bg-background px-1 py-0.5 text-[9px] font-medium text-muted-foreground">
              ?
            </kbd>{" "}
            for keyboard shortcuts
          </p>
        </div>

        <div className="mt-auto border-t border-border px-5 py-4 text-xs">
          {me?.founder ? (
            <>
              <p className="font-medium text-foreground">
                {me.founder.full_name}
              </p>
              <p className="text-muted-foreground">{me.founder.title}</p>
              <div className="mt-2">
                <Pillar pillar={me.founder.pillar} />
              </div>
            </>
          ) : me ? (
            <>
              <p className="font-medium text-foreground">{me.user_email}</p>
              <p className="mt-1 text-muted-foreground">
                Tenant member — not yet linked to a founder profile.
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">Loading session…</p>
          )}
        </div>
      </aside>

      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b border-border bg-card px-6 py-3">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            {me?.tenant ? (
              <>
                <span className="font-medium text-foreground">
                  {me.tenant.name}
                </span>
                <span className="text-muted-foreground/60">·</span>
                <span className="text-xs uppercase tracking-wider text-muted-foreground">
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

      {/* Linear-style keyboard shortcuts: g+letter for go-to nav, ?
          for the help modal. Mounts a single listener at the root. */}
      <KeyboardShortcuts />
    </div>
  );
}
