"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * KeyboardList — wraps a list of items so j/k moves selection between
 * them and Enter opens the highlighted one.
 *
 * Server pages render their list rows as anchors normally; this client
 * wrapper attaches a single keydown listener and uses the data
 * attributes on each child link to drive selection. That way list
 * pages don't need to become client components themselves.
 *
 * Conventions for caller markup:
 *   <KeyboardList>
 *     <ul>
 *       <li><Link href="..." data-kb-row>...</Link></li>
 *       ...
 *     </ul>
 *   </KeyboardList>
 *
 * Each direct anchor with `data-kb-row` is selectable. The current
 * selection scrolls into view + gets a brand-tinted ring (CSS class
 * `kb-selected`).
 *
 * j/k are ignored when:
 *   - any input/textarea/contenteditable has focus
 *   - any modal dialog (Cmd-K, shortcuts help) is open — detected by
 *     the presence of `[role="dialog"][aria-modal="true"]` in the DOM.
 */
export function KeyboardList({ children }: { children: React.ReactNode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const router = useRouter();

  // Re-query rows on every keypress so dynamic lists (filtering,
  // server-revalidation) stay in sync without explicit registration.
  function getRows(): HTMLAnchorElement[] {
    if (!containerRef.current) return [];
    return Array.from(
      containerRef.current.querySelectorAll<HTMLAnchorElement>(
        "a[data-kb-row]"
      )
    );
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Bail if user is typing.
      if (
        e.target instanceof HTMLElement &&
        (e.target.tagName === "INPUT" ||
          e.target.tagName === "TEXTAREA" ||
          e.target.isContentEditable)
      ) {
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      // Skip when a modal dialog is open. We don't want j/k to scroll
      // the underlying list while the user is in Cmd-K or shortcuts help.
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) {
        return;
      }
      const rows = getRows();
      if (rows.length === 0) return;

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIdx((prev) => {
          const next =
            prev === null ? 0 : Math.min(rows.length - 1, prev + 1);
          rows[next]?.scrollIntoView({ block: "nearest" });
          return next;
        });
        return;
      }
      if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIdx((prev) => {
          const next = prev === null ? 0 : Math.max(0, prev - 1);
          rows[next]?.scrollIntoView({ block: "nearest" });
          return next;
        });
        return;
      }
      if (e.key === "Enter" && selectedIdx !== null) {
        const row = rows[selectedIdx];
        if (row) {
          e.preventDefault();
          // Use the router for SPA-style nav so layouts persist.
          const href = row.getAttribute("href");
          if (href) router.push(href);
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router, selectedIdx]);

  // Apply / remove the .kb-selected class on the active row. We'd love
  // to use :has() but Safari support is good and Tailwind has
  // arbitrary variants — but a manual className toggle is simpler and
  // works in both server-rendered + client-revalidated trees.
  useEffect(() => {
    const rows = getRows();
    rows.forEach((r, i) => {
      if (i === selectedIdx) {
        r.classList.add("ring-2", "ring-brand-500", "ring-offset-1");
        r.setAttribute("aria-selected", "true");
      } else {
        r.classList.remove("ring-2", "ring-brand-500", "ring-offset-1");
        r.removeAttribute("aria-selected");
      }
    });
  }, [selectedIdx]);

  return <div ref={containerRef}>{children}</div>;
}
