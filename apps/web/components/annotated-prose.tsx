import type { ReactNode } from "react";
import { TermPopover } from "@/components/term-popover";

/**
 * AnnotatedProse — scan a free-text string (typically LLM-extracted from
 * a federal solicitation) and wrap recognized jargon in <TermPopover>
 * so a reader can hover any FAR/DFARS clause, section reference, NAICS
 * code, CMMC level, etc. and get a plain-English definition without
 * leaving the page.
 *
 * Detection is conservative on purpose: we only match patterns that
 * have an unambiguous canonical form in our explainer kinds. Free-text
 * "Section L", "Section M", "SOW", "PWS", "SOO", "CDRL" — yes. "Section
 * 2.3.4" — no. We'd rather miss a term than annotate noise.
 *
 * Recognized kinds (must mirror ALLOWED_KINDS in routes/explain.py):
 *   - clause:   FAR \d+\.\d+(-\d+)?  /  DFARS \d+\.\d+(-\d+)?
 *   - section:  Section L | M | J  ·  SOW · PWS · SOO · CDRL (standalone)
 *   - cmmc:     CMMC [Level] {1|2|3}
 *   - naics:    NAICS \d{6}
 *   - sprs:     SPRS (standalone)
 *   - cui / fci / itar / uei / cage / fcl  (standalone acronyms)
 *
 * Output preserves whitespace + non-matched text exactly. Matches inside
 * URLs / mailto links are skipped (we'd corrupt the link).
 */

type Match = { start: number; end: number; node: ReactNode; key: string };

// Order matters: longer / more specific patterns first so we don't
// shadow them. Each entry returns either a popover node or null
// (no annotation — useful for tightening false positives later).
const PATTERNS: Array<{
  re: RegExp;
  build: (m: RegExpExecArray, idx: number) => ReactNode | null;
}> = [
  // FAR / DFARS clause numbers — the most distinctive jargon. Match
  // "FAR 52.204-21" / "DFARS 252.204-7012" and minor variants. We
  // capture the whole token so the popover slug carries it intact.
  {
    re: /\b(?:DFARS|FAR)\s+\d{1,3}\.\d{1,4}(?:-\d{1,4})?\b/g,
    build: (m, idx) => (
      <TermPopover
        key={`clause-${idx}`}
        kind="clause"
        value={m[0].replace(/\s+/g, " ")}
      >
        {m[0]}
      </TermPopover>
    ),
  },
  // CMMC Level — "CMMC Level 2", "CMMC 2", "CMMC L2"
  {
    re: /\bCMMC(?:\s+(?:Level|L))?\s*([123])\b/g,
    build: (m, idx) => (
      <TermPopover key={`cmmc-${idx}`} kind="cmmc" value={`Level ${m[1]}`}>
        {m[0]}
      </TermPopover>
    ),
  },
  // NIST SP 800-171 / 800-172 — common in cyber-posture prose
  {
    re: /\bNIST(?:\s+SP)?\s*800-(?:171|172)\b/g,
    build: (m, idx) => (
      <TermPopover
        key={`nist-${idx}`}
        kind="clause"
        value={m[0].replace(/\s+/g, " ")}
      >
        {m[0]}
      </TermPopover>
    ),
  },
  // NAICS code — "NAICS 541512"
  {
    re: /\bNAICS\s+(\d{6})\b/g,
    build: (m, idx) => (
      <TermPopover key={`naics-${idx}`} kind="naics" value={m[1]}>
        {m[0]}
      </TermPopover>
    ),
  },
  // Section L / M / J — the eval-factor + instructions sections.
  // We deliberately don't match "Section 3.1.4" style pointers.
  {
    re: /\bSection\s+([LMJ])\b/g,
    build: (m, idx) => (
      <TermPopover key={`section-${idx}`} kind="section" value={m[1]}>
        {m[0]}
      </TermPopover>
    ),
  },
  // Standalone solicitation-section acronyms — only when surrounded
  // by word boundaries. Tight regex to avoid mid-word noise.
  {
    re: /\b(SOW|PWS|SOO|CDRL)\b/g,
    build: (m, idx) => (
      <TermPopover key={`sec-acr-${idx}`} kind="section" value={m[1]}>
        {m[0]}
      </TermPopover>
    ),
  },
  // SPRS — standalone, all caps. Won't match "sprs" lowercase by
  // design; that's almost always not the assessment system.
  {
    re: /\bSPRS\b/g,
    build: (m, idx) => (
      <TermPopover key={`sprs-${idx}`} kind="sprs" value="score">
        {m[0]}
      </TermPopover>
    ),
  },
  // Standalone acronyms with single canonical kind. CAGE deliberately
  // included because "CAGE code" is the common phrase in solicitations.
  {
    re: /\b(CUI|FCI|ITAR|UEI|CAGE|FCL)\b/g,
    build: (m, idx) => {
      const tag = m[1].toLowerCase();
      return (
        <TermPopover key={`acr-${tag}-${idx}`} kind={tag} value={tag}>
          {m[0]}
        </TermPopover>
      );
    },
  },
];

// URLs we must not touch — annotating "FAR 52.204-21" inside a link
// would break the anchor. Conservative: skip entire URL spans.
const URL_RE = /https?:\/\/[^\s)>\]]+|mailto:[^\s)>\]]+/g;

function findMatches(text: string): Match[] {
  // First, mark URL ranges so we can skip them.
  const skipRanges: Array<[number, number]> = [];
  for (const m of text.matchAll(URL_RE)) {
    skipRanges.push([m.index!, m.index! + m[0].length]);
  }
  const inSkip = (i: number) =>
    skipRanges.some(([s, e]) => i >= s && i < e);

  const matches: Match[] = [];
  let key = 0;
  for (const { re, build } of PATTERNS) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      const start = m.index;
      const end = start + m[0].length;
      if (inSkip(start)) continue;
      // Suppress overlapping later patterns: if this start is inside an
      // already-recorded match, skip.
      if (matches.some((x) => start < x.end && end > x.start)) continue;
      const node = build(m, key++);
      if (node !== null) {
        matches.push({ start, end, node, key: `${re.source}-${start}` });
      }
    }
  }
  matches.sort((a, b) => a.start - b.start);
  return matches;
}

export function AnnotatedProse({
  text,
  className = "",
}: {
  text: string | null | undefined;
  className?: string;
}) {
  if (!text) return null;
  const matches = findMatches(text);
  if (matches.length === 0) {
    return <span className={className}>{text}</span>;
  }
  const out: ReactNode[] = [];
  let cursor = 0;
  matches.forEach((m, i) => {
    if (cursor < m.start) {
      out.push(text.slice(cursor, m.start));
    }
    out.push(<span key={`m-${i}`}>{m.node}</span>);
    cursor = m.end;
  });
  if (cursor < text.length) {
    out.push(text.slice(cursor));
  }
  return <span className={className}>{out}</span>;
}
