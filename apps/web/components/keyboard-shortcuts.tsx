"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * KeyboardShortcuts — global keybindings, Linear-style.
 *
 * Bindings:
 *   g d → /dashboard
 *   g o → /opportunities
 *   g p → /pipeline
 *   g f → /forecasts
 *   g r → /recompetes
 *   g e → /events
 *   g l → /library
 *   g s → /settings
 *   g x → /drafts                  (x = "draftX")
 *   ? or shift-/ → open help modal
 *   esc → close help modal
 *
 * Cmd-K / Ctrl-K is owned by <CmdK /> (the global search modal). We
 * deliberately don't bind it again here.
 *
 * The "g" prefix is a Linear/Vim convention: the user presses g, then
 * has ~1s to press a destination letter. If they don't, the timer
 * resets. Pressing any non-destination letter cancels.
 *
 * We ignore all keys when the user is typing in an input, textarea,
 * contenteditable, or has Cmd-K open (so search query input still works).
 */

const ROUTES: Record<string, { href: string; label: string }> = {
  d: { href: "/dashboard", label: "Dashboard" },
  o: { href: "/opportunities", label: "Opportunities" },
  p: { href: "/pipeline", label: "Pipeline" },
  f: { href: "/forecasts", label: "Forecasts" },
  r: { href: "/recompetes", label: "Recompetes" },
  e: { href: "/events", label: "Events" },
  l: { href: "/library", label: "Library" },
  s: { href: "/settings", label: "Settings" },
  x: { href: "/drafts", label: "Drafts" },
};

const PREFIX_TIMEOUT_MS = 1500;

function isTypingTarget(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  const tag = t.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (t.isContentEditable) return true;
  // CmdK modal is itself a dialog; skip while it's open. We detect by
  // looking for the role="dialog" ancestor, since the modal's input is
  // already covered by INPUT above.
  return false;
}

export function KeyboardShortcuts() {
  const router = useRouter();
  const [helpOpen, setHelpOpen] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  useEffect(() => {
    let prefixTimer: ReturnType<typeof setTimeout> | null = null;
    let inGPrefix = false;

    function clearPrefix() {
      if (prefixTimer) {
        clearTimeout(prefixTimer);
        prefixTimer = null;
      }
      inGPrefix = false;
      setHint(null);
    }

    function onKeyDown(e: KeyboardEvent) {
      // Bail when user is typing or modifier keys (Cmd-K etc) are in play.
      if (isTypingTarget(e.target)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      // Esc: close help modal first; don't consume otherwise.
      if (e.key === "Escape") {
        if (helpOpen) {
          setHelpOpen(false);
          e.preventDefault();
        }
        clearPrefix();
        return;
      }

      // ? — open help. Browsers may report shift-/ depending on layout;
      // accept either.
      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        setHelpOpen((v) => !v);
        clearPrefix();
        return;
      }

      // g prefix
      if (!inGPrefix && e.key.toLowerCase() === "g") {
        inGPrefix = true;
        setHint("g · then d/o/p/f/r/e/l/s/x");
        prefixTimer = setTimeout(clearPrefix, PREFIX_TIMEOUT_MS);
        // Don't preventDefault — if user really wanted to type "g" in a
        // non-input element, this is a no-op anyway, and we want native
        // focus-key behavior to keep working.
        return;
      }

      if (inGPrefix) {
        const dest = ROUTES[e.key.toLowerCase()];
        clearPrefix();
        if (dest) {
          e.preventDefault();
          router.push(dest.href);
        }
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      if (prefixTimer) clearTimeout(prefixTimer);
    };
  }, [router, helpOpen]);

  return (
    <>
      {/* Floating prefix hint — appears for ~1.5s after pressing 'g' */}
      {hint && (
        <div
          aria-live="polite"
          className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 shadow-md"
        >
          {hint}
        </div>
      )}
      {helpOpen && (
        <ShortcutsHelp onClose={() => setHelpOpen(false)} />
      )}
    </>
  );
}

function ShortcutsHelp({ onClose }: { onClose: () => void }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
    >
      <button
        type="button"
        aria-label="Close shortcuts"
        onClick={onClose}
        className="fixed inset-0 bg-neutral-900/30 backdrop-blur-sm"
      />
      <div className="relative w-full max-w-lg overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-2xl">
        <header className="flex items-center justify-between border-b border-neutral-200 px-5 py-3">
          <p className="text-sm font-semibold text-neutral-900">
            Keyboard shortcuts
          </p>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700"
            aria-label="Close"
          >
            ✕
          </button>
        </header>
        <div className="grid grid-cols-1 gap-x-8 gap-y-3 px-5 py-4 text-sm md:grid-cols-2">
          <ShortcutGroup title="Navigation">
            <Shortcut keys={["g", "d"]} label="Dashboard" />
            <Shortcut keys={["g", "o"]} label="Opportunities" />
            <Shortcut keys={["g", "p"]} label="Pipeline" />
            <Shortcut keys={["g", "f"]} label="Forecasts" />
            <Shortcut keys={["g", "r"]} label="Recompetes" />
            <Shortcut keys={["g", "e"]} label="Events" />
            <Shortcut keys={["g", "l"]} label="Library" />
            <Shortcut keys={["g", "x"]} label="Drafts" />
            <Shortcut keys={["g", "s"]} label="Settings" />
          </ShortcutGroup>
          <ShortcutGroup title="Within lists">
            <Shortcut keys={["j"]} label="Next item" />
            <Shortcut keys={["k"]} label="Previous item" />
            <Shortcut keys={["Enter"]} label="Open selected" />
          </ShortcutGroup>
          <ShortcutGroup title="Anywhere">
            <Shortcut keys={["⌘", "K"]} label="Search" />
            <Shortcut keys={["?"]} label="This help" />
            <Shortcut keys={["Esc"]} label="Close modals / clear" />
          </ShortcutGroup>
        </div>
        <footer className="border-t border-neutral-200 bg-neutral-50 px-5 py-2 text-[11px] text-neutral-500">
          Tip: shortcuts are ignored while typing in any input or textarea.
        </footer>
      </div>
    </div>
  );
}

function ShortcutGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
        {title}
      </p>
      <ul className="space-y-1">{children}</ul>
    </div>
  );
}

function Shortcut({ keys, label }: { keys: string[]; label: string }) {
  return (
    <li className="flex items-center justify-between gap-3">
      <span className="text-neutral-700">{label}</span>
      <span className="flex items-center gap-1">
        {keys.map((k, i) => (
          <kbd
            key={i}
            className="rounded border border-neutral-200 bg-neutral-50 px-1.5 py-0.5 text-[10px] font-medium text-neutral-700"
          >
            {k}
          </kbd>
        ))}
      </span>
    </li>
  );
}
