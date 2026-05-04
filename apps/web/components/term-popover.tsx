"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import type { TermExplanationResponse } from "@/lib/api";

/**
 * TermPopover — inline jargon explainer that opens in place, no
 * navigation. The companion to <Term> (which links to ?explain= and
 * opens the right-hand ExplainRail).
 *
 * Use TermPopover on surfaces WITHOUT a rail (dashboard, list pages,
 * inline-prose snippets), and Term on surfaces that already have the
 * rail wired (opportunity / pursuit / capture-package detail).
 *
 * Behavior:
 *   - Hover or focus opens. Click pins so it stays open until the user
 *     clicks elsewhere or presses Esc.
 *   - First open lazy-fetches /explain/{slug}. Subsequent opens reuse
 *     the in-memory cache for that mount. The backend keeps a per-slug
 *     row cache so the LLM only ever runs once per term across the app.
 *   - "Learn more →" links to ?explain= so users on a rail-supporting
 *     page can promote the popover to the full rail.
 *
 * Accessibility:
 *   - Trigger is a real <button> with aria-expanded + aria-controls.
 *   - Popover has role="dialog" + aria-labelledby and Esc closes it.
 *   - Hover delay (200ms in / 150ms out) prevents flicker; reduced
 *     motion users still get the open/close transitions.
 */

// In-flight + completed lookups per slug. Sharing across all popover
// instances so re-mounting (e.g. clicking Term in a re-rendered list)
// doesn't refire the network call.
const TERM_CACHE = new Map<string, Promise<TermExplanationResponse | null>>();

function fetchExplanation(
  slug: string,
): Promise<TermExplanationResponse | null> {
  let inflight = TERM_CACHE.get(slug);
  if (inflight) return inflight;
  inflight = fetch(`/api/explain/${encodeURIComponent(slug)}`, {
    headers: { "x-cache-source": "term-popover" },
    cache: "force-cache",
  })
    .then(async (r) => {
      if (!r.ok) return null;
      return (await r.json()) as TermExplanationResponse;
    })
    .catch(() => null);
  TERM_CACHE.set(slug, inflight);
  return inflight;
}

const HOVER_OPEN_MS = 200;
const HOVER_CLOSE_MS = 150;

export function TermPopover({
  kind,
  value,
  children,
  className = "",
  /** When true, render an inline-link "Learn more →" inside the
   * popover that promotes to ?explain= for full-rail pages. Default
   * true; set false on pages that don't support the rail. */
  showLearnMore = true,
}: {
  kind: string;
  value: string;
  children?: React.ReactNode;
  className?: string;
  showLearnMore?: boolean;
}) {
  const slug = `${kind}:${value}`;
  const labelText =
    typeof children === "string" ? children : value;

  const triggerId = useId();
  const popoverId = useId();

  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [explanation, setExplanation] = useState<
    TermExplanationResponse | null | "loading"
  >(null);

  const hoverInTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hoverOutTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLSpanElement>(null);

  // Click outside / Esc closes when pinned.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!wrapperRef.current) return;
      if (!wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
        setPinned(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        setPinned(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Lazy-fetch on first open.
  useEffect(() => {
    if (!open || explanation !== null) return;
    setExplanation("loading");
    fetchExplanation(slug).then((res) => setExplanation(res));
  }, [open, slug, explanation]);

  function clearTimers() {
    if (hoverInTimer.current) {
      clearTimeout(hoverInTimer.current);
      hoverInTimer.current = null;
    }
    if (hoverOutTimer.current) {
      clearTimeout(hoverOutTimer.current);
      hoverOutTimer.current = null;
    }
  }

  function scheduleOpen() {
    if (pinned || open) return;
    clearTimers();
    hoverInTimer.current = setTimeout(() => setOpen(true), HOVER_OPEN_MS);
  }

  function scheduleClose() {
    if (pinned) return;
    clearTimers();
    hoverOutTimer.current = setTimeout(() => setOpen(false), HOVER_CLOSE_MS);
  }

  function togglePin(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    clearTimers();
    if (pinned) {
      setPinned(false);
      setOpen(false);
    } else {
      setPinned(true);
      setOpen(true);
    }
  }

  return (
    <span
      ref={wrapperRef}
      className={`relative inline-flex ${className}`}
      onMouseEnter={scheduleOpen}
      onMouseLeave={scheduleClose}
    >
      <button
        id={triggerId}
        type="button"
        aria-expanded={open}
        aria-controls={popoverId}
        aria-label={`${labelText} — what is this?`}
        onFocus={scheduleOpen}
        onBlur={scheduleClose}
        onClick={togglePin}
        className="inline-flex items-baseline gap-0.5 border-b border-dotted border-brand-300/70 leading-tight text-current hover:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-sm"
      >
        <span>{children ?? value}</span>
        <span aria-hidden className="text-[9px] text-brand-700">?</span>
      </button>

      {open && (
        <div
          id={popoverId}
          role="dialog"
          aria-labelledby={triggerId}
          className="absolute left-0 top-[calc(100%+6px)] z-30 w-80 max-w-[min(20rem,90vw)] rounded-md border border-brand-200 bg-white p-3 shadow-lg"
          onMouseEnter={() => clearTimers()}
          onMouseLeave={scheduleClose}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-[10px] font-medium uppercase tracking-wide text-brand-700">
              Explain this
            </p>
            {pinned && (
              <button
                type="button"
                onClick={() => {
                  setPinned(false);
                  setOpen(false);
                }}
                className="rounded p-0.5 text-neutral-400 hover:bg-paper-100 hover:text-neutral-700"
                aria-label="Close"
              >
                ✕
              </button>
            )}
          </div>

          {explanation === "loading" || explanation === null ? (
            <p className="mt-1 text-sm text-neutral-500">
              Looking up <span className="font-mono">{slug}</span>…
            </p>
          ) : explanation ? (
            <>
              <h4 className="mt-0.5 text-sm font-semibold text-neutral-900">
                {explanation.label}
              </h4>
              <p className="mt-1 text-[13px] leading-relaxed text-neutral-700">
                {explanation.summary}
              </p>
              {showLearnMore && (
                <Link
                  href={`?explain=${encodeURIComponent(slug)}`}
                  scroll={false}
                  className="mt-2 inline-block text-[11px] font-medium text-brand-700 hover:underline"
                  onClick={() => {
                    setPinned(false);
                    setOpen(false);
                  }}
                >
                  Read full explanation →
                </Link>
              )}
            </>
          ) : (
            <p className="mt-1 text-sm text-neutral-600">
              Couldn&rsquo;t load an explanation. Hover again to retry.
            </p>
          )}
        </div>
      )}
    </span>
  );
}
