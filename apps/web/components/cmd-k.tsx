"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { searchEverything } from "@/lib/search";
import type { SearchHit, SearchHitKind, SearchResponse } from "@/lib/api";

const KIND_LABELS: Record<SearchHitKind, string> = {
  opportunity: "Opportunities",
  draft: "Drafts",
  teaming_partner: "Teaming partners",
  past_performance: "Past performance"
};

const KIND_ORDER: SearchHitKind[] = [
  "opportunity",
  "draft",
  "teaming_partner",
  "past_performance"
];

const DEBOUNCE_MS = 200;

export function CmdK() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [isPending, startTransition] = useTransition();
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // Global Cmd-K / Ctrl-K to toggle.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
        return;
      }
      if (open && e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  // Focus the input on open.
  useEffect(() => {
    if (open) {
      // Slight delay so the modal mounts first.
      const t = setTimeout(() => inputRef.current?.focus(), 10);
      return () => clearTimeout(t);
    }
  }, [open]);

  // Debounced search.
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => {
      startTransition(async () => {
        try {
          const data = await searchEverything(query);
          setResults(data);
          setActiveIdx(0);
        } catch (err) {
          console.error("global search failed", err);
        }
      });
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [open, query]);

  const flat = flattenResults(results);
  const grouped = results?.grouped ?? null;

  function navigateActive() {
    const hit = flat[activeIdx];
    if (!hit) return;
    setOpen(false);
    setQuery("");
    setResults(null);
    router.push(hit.url);
  }

  function onInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, Math.max(0, flat.length - 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      navigateActive();
    }
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Global search"
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[15vh]"
    >
      {/* Click-outside scrim */}
      <button
        type="button"
        aria-label="Close search"
        onClick={() => setOpen(false)}
        className="fixed inset-0 bg-neutral-900/30 backdrop-blur-sm"
      />
      <div className="relative w-full max-w-xl overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-2xl">
        <div className="flex items-center gap-2 border-b border-neutral-200 px-4 py-3">
          <svg
            aria-hidden
            viewBox="0 0 16 16"
            className="h-4 w-4 shrink-0 text-neutral-400"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="7" cy="7" r="5" />
            <path d="M11 11l3 3" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder="Search opportunities, drafts, partners…"
            className="min-w-0 flex-1 bg-transparent text-base text-neutral-900 placeholder:text-neutral-400 focus:outline-none"
            aria-label="Search query"
          />
          <kbd className="rounded border border-neutral-200 bg-neutral-50 px-1.5 py-0.5 text-[10px] font-medium text-neutral-500">
            esc
          </kbd>
        </div>

        <div className="max-h-[60vh] overflow-y-auto">
          {isPending && (
            <p className="px-4 py-3 text-xs text-neutral-500">Searching…</p>
          )}
          {!isPending && results && results.total === 0 && (
            <p className="px-4 py-6 text-center text-sm text-neutral-500">
              No matches{query ? ` for "${query}"` : ""}.
            </p>
          )}
          {!isPending && grouped && results && results.total > 0 && (
            <div className="py-1">
              {KIND_ORDER.map((kind) => {
                const items = grouped[kind] ?? [];
                if (items.length === 0) return null;
                return (
                  <section key={kind} aria-label={KIND_LABELS[kind]}>
                    <p className="px-4 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
                      {KIND_LABELS[kind]}
                    </p>
                    <ul>
                      {items.map((hit) => {
                        const flatIdx = flat.findIndex(
                          (h) => h.kind === hit.kind && h.id === hit.id
                        );
                        const active = flatIdx === activeIdx;
                        return (
                          <li key={`${hit.kind}-${hit.id}`}>
                            <button
                              type="button"
                              onMouseEnter={() => setActiveIdx(flatIdx)}
                              onClick={() => {
                                setActiveIdx(flatIdx);
                                navigateActive();
                              }}
                              className={
                                active
                                  ? "block w-full bg-brand-50 px-4 py-2 text-left"
                                  : "block w-full px-4 py-2 text-left hover:bg-neutral-50"
                              }
                            >
                              <p className="truncate text-sm font-medium text-neutral-900">
                                {hit.title}
                              </p>
                              {hit.subtitle && (
                                <p className="truncate text-xs text-neutral-500">
                                  {hit.subtitle}
                                </p>
                              )}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}
            </div>
          )}
          {!isPending && !results && (
            <p className="px-4 py-6 text-center text-sm text-neutral-500">
              Start typing to search…
            </p>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-neutral-200 bg-neutral-50 px-4 py-2 text-[11px] text-neutral-500">
          <span>
            {flat.length} result{flat.length === 1 ? "" : "s"}
          </span>
          <span className="space-x-3">
            <span>
              <kbd className="rounded border border-neutral-200 bg-white px-1 text-[10px]">
                ↑↓
              </kbd>{" "}
              navigate
            </span>
            <span>
              <kbd className="rounded border border-neutral-200 bg-white px-1 text-[10px]">
                ↵
              </kbd>{" "}
              open
            </span>
            <span>
              <kbd className="rounded border border-neutral-200 bg-white px-1 text-[10px]">
                esc
              </kbd>{" "}
              close
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}

export function CmdKTrigger() {
  const [open, setOpen] = useState(false);
  // Listen for the same Cmd-K so the trigger label can pulse if we want
  // visual feedback later. For now this is purely a button that fires the
  // same keypress on click via dispatchEvent.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        setOpen((v) => !v);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
  return (
    <button
      type="button"
      onClick={() => {
        // Synthesize the keystroke so the modal toggles via its own listener.
        window.dispatchEvent(
          new KeyboardEvent("keydown", { key: "k", metaKey: true })
        );
      }}
      className="flex w-full items-center justify-between gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs text-neutral-500 transition-colors hover:border-neutral-400 hover:text-neutral-700"
      aria-label="Open global search"
      title="Open global search (⌘K / Ctrl+K)"
    >
      <span className="flex items-center gap-2">
        <svg
          aria-hidden
          viewBox="0 0 16 16"
          className="h-3.5 w-3.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="7" cy="7" r="5" />
          <path d="M11 11l3 3" strokeLinecap="round" />
        </svg>
        Search…
      </span>
      <kbd className="rounded border border-neutral-200 bg-white px-1 py-0.5 text-[10px] font-medium text-neutral-500">
        ⌘K
      </kbd>
      {/* Mirror state into the DOM via aria-pressed for a11y, keeping the
          actual modal state inside <CmdK />. */}
      <span aria-pressed={open} hidden />
    </button>
  );
}

function flattenResults(r: SearchResponse | null): SearchHit[] {
  if (!r) return [];
  const grouped = r.grouped;
  const out: SearchHit[] = [];
  for (const kind of KIND_ORDER) {
    const items = grouped[kind] ?? [];
    out.push(...items);
  }
  return out;
}
