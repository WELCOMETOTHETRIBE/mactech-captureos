# Verification Report
For change-log: 2026-05-25T12:35:00-07:00 (pass 2)
Iteration: 1
Generated: 2026-05-25T13:10:00-07:00

## Verdict
**SHIP**

Headline: all five leverage points from pass-2 brief §7 are present in the
diff against `main` HEAD, the architect's design contract has been honored
in code, `tsc --noEmit` exits 0, `next build` exits 0 with all 35 routes
compiled (unchanged route count vs. pass 1), the `--high-moat` token is
preserved at `45 90% 28%`, no new hex literals or emoji were introduced,
and the pass-1 surfaces (TodaysMoves, globals.css, score worker, HpewBadge
primitive, sweet-spot row treatment) are untouched.

The same Clerk-session limitation from pass-1 verification still applies —
`/dashboard` and `/opportunities` cannot be rendered in this environment
without a Clerk JWT (`apiFetch called without a Clerk session — guard the
route` thrown by `lib/api.ts:18`). Per the user's standing instruction
across this verification loop, this is treated as an environment
limitation and is NOT a SHIP blocker. Code-level evidence is strong; a
logged-in human eyeball pass on the new detail render order + the gold
high-moat strip is recommended before stakeholder demo.

## Success criteria evaluation (brief §9)

| Criterion | Status | Evidence |
|---|---|---|
| Detail page first-scroll: PageHeader → meta → high-moat strip (if gated) → brief panel; PursuitPanel/DrafterPanel/AskPanel NOT above the fold | Met (code-verified) | `[id]/page.tsx` lines 220–357 — render order is PageHeader → meta → `<HighMoatStrip score={data.score} />` (line 241) → two-column main (line 247) → "Take action" section (line 336) wrapping the three post-decision panels |
| HighMoat strip gated to `score.high_moat && score.high_moat.score >= 70`; absent when gate fails | Met (code-verified) | `[id]/page.tsx` lines 509–512: `if (!score \|\| !score.high_moat) return null;` then `if (hm.score < 70) return null;` |
| HighMoat strip uses 3px `border-l-[hsl(var(--high-moat))]`, no gold fill or tint | Met (code-verified) | `[id]/page.tsx` line 521 — `rounded-md border border-border border-l-[3px] border-l-[hsl(var(--high-moat))] bg-card p-5` — no `bg-[hsl(var(--high-moat))]` or tint anywhere in the component |
| HighMoat strip surfaces `why_it_matters_seed`, `clause_hits`, `top_clearance` (when != "NONE"), `role_hits` | Met (code-verified) | `[id]/page.tsx` lines 514–589; `top_clearance` filtered at line 515 (`hm.top_clearance && hm.top_clearance !== "NONE"`); fallback message when `why_it_matters_seed` is null at lines 538–544 |
| `ScoreBlock` includes `high_moat: HighMoatBlock \| null` with 8 fields | Met (code-verified) | `lib/api.ts` lines 276–285 (HighMoatBlock with all 8 fields), 298 (`high_moat: HighMoatBlock \| null` on ScoreBlock); `tsc --noEmit` exit 0 |
| Perspective rail on `/opportunities` with founder-private filter | Met (code-verified) | `opportunities/page.tsx` lines 94–96 — `owner_founder_slug === mySlug \|\| owner_founder_slug === null`; rail renders "All opportunities" first then user's perspectives (lines 600–622) |
| Clicking perspective navigates to `/opportunities?saved_search={id}`; subtitle changes | Met (code-verified) | `opportunities/page.tsx` lines 609–615 (`qs.set("saved_search", p.id)`); subtitle at lines 167–169 leads with "Perspective: ..." when active |
| Filter facets reachable from collapsible "Refine this view"; open when no perspective active | Met (code-verified) | `opportunities/page.tsx` lines 307–377; `{...(activePerspective ? {} : { open: true })}` at line 309 |
| Brief/raw tabs use `?view=brief\|raw` search param; active filled, inactive bordered | Met (code-verified) | `[id]/page.tsx` lines 91 (`view?: string` searchParam), 99 (sanitized), 1056–1065 (tab href + visual classes); active uses `bg-primary text-primary-foreground`, inactive `border border-border` |
| BriefList violet tone routes through token, not raw violet palette | Met (code-verified) | `[id]/page.tsx` lines 1246–1257 — `violet: "text-muted-foreground"` / `violet: "bg-muted-foreground"`; `grep -E "text-violet\|bg-violet" [id]/page.tsx` returns ZERO hits |
| Dashboard KPI strip = 3 tiles; "Sweet spots today" leads with gold ink when >0 / neutral when 0 | Met (code-verified) | `dashboard/page.tsx` line 274 (`md:grid-cols-3`); lines 283–290 — `tone={data.kpis.your_sweet_spots_open > 0 ? "high_moat" : "neutral"}` |
| Active pursuits + Drafts to review demoted to text line under TodaysMoves | Met (code-verified) | `dashboard/page.tsx` lines 364–385 (after `TodaysMoves` block at 347–357) — single `<p>` with "Your work:" + two inline `<Link>` segments |
| `CyberPostureCard` symbol renamed to `CyberFitCard` with new visible title | Met (code-verified) | `components/cyber-posture-card.tsx` line 17 (`export function CyberFitCard`), line 26 (`<Card title="Cyber fit · your posture vs. their ask">`); back-compat alias at line 249 (`export const CyberPostureCard = CyberFitCard`) |
| Import in `[id]/page.tsx` updated to `CyberFitCard` | Met (code-verified) | `[id]/page.tsx` line 257 (`{cyberSummary && <CyberFitCard summary={cyberSummary} />}`) |
| "What's missing" sub-rail surface exists; renders nothing when list empty | Met (code-verified) | `cyber-posture-card.tsx` lines 222–240 — `MissingClausesRail` with `if (clauses.length === 0) return null;`; mounted at line 35 with `summary.missing_clauses ?? []` |
| "Open detail →" line removed from dashboard "Your top" rows | Met (code-verified) | `dashboard/page.tsx` lines 504–506 (replaced with pass-2 explanation comment); no `Open detail →` literal anywhere |
| Row hover swap: `hover:shadow-sm` → `hover:bg-accent/40` on both /dashboard + /opportunities | Met (code-verified) | `dashboard/page.tsx` lines 438–439 (both sweet-spot and standard variants); `opportunities/page.tsx` lines 456–457 (same on list rows) |
| Sweet-spot rows preserve gold left border on hover | Met (code-verified) | `dashboard/page.tsx` line 438 — `border-l-[3px] border-l-[hsl(var(--high-moat))]` lives in the BASE class so hover doesn't strip it; same shape on `opportunities/page.tsx` line 456 |
| `--high-moat` token unchanged at `45 90% 28%` | Met (audit-verified) | `git diff HEAD -- apps/web/app/globals.css` returns zero diff; `grep -n high-moat apps/web/app/globals.css` → `--high-moat: 45 90% 28%;` at line 84 |
| Contrast preserved on all new `--high-moat` callsites | Met (math-inherited from pass 1) | Token value unchanged → pass-1 iteration-3 measurements still valid: 4.97:1 on paper, 5.24:1 on white card (both clear 4.5:1 text bar with headroom; left rail clears 3:1 non-text bar) |
| No new emoji in product UI | Met (grep-verified) | `git diff HEAD -- 'apps/web'` filtered through Unicode-emoji range grep returns zero hits |
| No new hardcoded hex literals | Met (grep-verified) | `git diff HEAD -- 'apps/web/**/*.tsx' 'apps/web/**/*.ts'` filtered for `#[0-9A-Fa-f]{3,8}` on added lines returns zero hits |
| No new `console.log` / undated `TODO` / `: any` types | Met (grep-verified) | Same diff filtered for these patterns returns zero hits |
| `tsc --noEmit` exits 0 | Met (verified) | `cd apps/web && npx tsc --noEmit` → exit 0, no output |
| `next build` exits 0 | Met (verified) | `cd apps/web && npx next build` → exit 0, 35 routes compiled (same as pass 1) |
| Pass-1 surfaces untouched (TodaysMoves, globals.css, score worker) | Met (audit-verified) | `git diff HEAD -- apps/web/components/todays-moves.tsx apps/web/app/globals.css apps/workers/src/mactech_workers/tasks/score.py` → 0 lines diff |
| HpewBadge primitive untouched | Met (verified) | `apps/web/components/ui.tsx` HpewBadge at line 223 — `git diff HEAD -- apps/web/components/ui.tsx` shows only the `Kpi` tone-union extension (`high_moat` added); no edit to HpewBadge |
| Protected-route visual confirmation | Untestable in this env | `/dashboard` and `/opportunities` 500 with `apiFetch called without a Clerk session` — same Clerk session limitation as pass-1; per user instruction NOT a SHIP blocker when code evidence is strong |

## Accessibility findings

- **Critical violations:** 0 (surfaces inspected via code; computed contrast preserved)
- **Serious violations:** 0
- **Contrast failures on changed surfaces:** 0. The `--high-moat` token
  is unchanged from pass-1 iteration 3 (`45 90% 28%`), so all four
  measured ratios from pass 1 still hold:
  - HpewBadge text on white card: **5.243:1** (clears 4.5:1)
  - Sweet-spots toggle text on paper-50: **4.966:1** (clears 4.5:1)
  - 3px gold left rail on card: **4.966:1** (clears 3:1 non-text)
  - HighMoatStrip eyebrow text (new callsite this pass, same token):
    inherits 5.243:1 on white card — clears 4.5:1
  - Kpi `tone="high_moat"` value text (new callsite this pass, same
    token): inherits 5.243:1 on white card — clears 4.5:1
- **Focus indicator issues:** Not re-tested this iteration (no
  focus-state code change). Prior iterations did not flag any.
- **Pre-existing `/sign-in` "APPS" footer label (4.10:1)** still
  present. Pre-existing tech debt, excluded by user instruction.

## Responsiveness findings

No layout / breakpoint code touched this pass that would affect
responsive behavior. KPI grid changed from `md:grid-cols-4` to
`md:grid-cols-3`; the two-column detail-page main and the
perspective-rail-plus-results 4-column dashboard grid (`lg:grid-cols-4`
with rail at `lg:col-span-1` + results at `lg:col-span-3`) are mobile-
first stacked with `grid-cols-1` at small viewports. The HighMoatStrip
uses `grid-cols-1 lg:grid-cols-2` with the right-side meta grid using
`grid-cols-1 sm:grid-cols-3`. All responsive layouts collapse cleanly
to a single column at 375px.

## State coverage

For components touched this pass:

- **HighMoatStrip**: empty/null `score.high_moat` → returns null (absent
  from DOM); below-threshold (`score < 70`) → returns null; null
  `why_it_matters_seed` → fallback message rendered; empty
  `clause_hits` / `role_hits` / `NONE` clearance → those columns
  conditionally skipped (`hasClauses`, `hasClearance`, `hasRoles`
  guards at lines 514–516)
- **PerspectiveRail**: empty `perspectives` array → "All opportunities"
  still renders alone (no inline CTA per brief §11 Q3); unknown
  `saved_search` id → silently falls through to "All opportunities"
  (line 102 `find(...) ?? null`)
- **BriefAndDescriptionPanel**: brief exists → defaults to `view=brief`;
  brief is null → defaults to `view=raw`; both states render their
  respective `tabpanel` cleanly. `?view=garbage` → sanitized to null,
  falls back to the natural default
- **CyberFitCard / MissingClausesRail**: `missing_clauses` absent or
  empty → rail returns null; populated → renders neutral badge list
  with warning-tone eyebrow

## Aesthetic adherence

- **Brief endorsed (§6):** editorial / B2G credibility — warm-paper,
  brand-teal, editorial-serif headers, restrained gold accent. No
  glass, no dark mode, no cyan, no neon, no animation, no
  illustration, no emoji.
- **Implementation matches:** yes. The HighMoatStrip composition is
  3px gold left rail + white card chrome + ink-only gold accent (no
  fill, no tint). The italic-serif treatment on `why_it_matters_seed`
  (line 534, `font-medium italic leading-snug font-serif`) echoes the
  page H1's serif treatment. The Perspective rail's active-state
  visual (`border-l-2 border-primary bg-primary/10`) mirrors the
  SidebarNav pattern — visual language stays consistent across
  chrome surfaces. The Kpi `tone="high_moat"` is ink-only — no fill,
  no glow.
- **Specific divergences:** none observed.

## Screenshots

No new screenshots this pass — protected-route screenshot verification
is environmentally blocked (no Clerk session — same constraint as
pass 1). The architect's change-log § "Visual diff: NOT RUN"
explicitly acknowledges this and the brief explicitly says not to
treat this as a SHIP blocker if code-level evidence is strong.

## Items requiring iteration

None. All five leverage points are present, gated correctly, token-
disciplined, and pass typecheck + build. The architect's change log
is precise and matches the diff against `main` HEAD.

## Items requiring human decision

1. **Eyeball pass on the new detail render order** — does the bid/no-bid
   triage feel right above the fold? The HighMoatStrip on a real
   high-moat opp (e.g., a Patrick UFGS 25 / FRCS Cyber opp) — does the
   3px gold rail read as "embossed seal" against the warm paper-50
   background, or as "muddy brown"? Recommend one of the four founders
   (Patrick most natural fit given the UFGS perspective seeded for him)
   log in and walk through 3 high-moat opps on the new page.
2. **Perspective rail behavior for Patrick** — Patrick has two saved
   searches with very different intents (Security daily broad cyber vs.
   UFGS 25 narrow track). Does the named-perspective switcher actually
   feel faster than typing query strings? And does the UFGS perspective
   return a non-empty result set after the high-moat scorer has run on
   the current feed? The architect's known-limitation #1 explicitly
   flags this as the most important logged-in eyeball question.
3. **Backend `missing_clauses` field** — the UI surface is wired; the
   backend currently returns the field absent, so the "What's missing"
   sub-rail renders nothing on day one. The cross-reference logic
   (cited clauses minus tenant evidence) is the only remaining work to
   light up the surface — explicitly marked as `TODO(pass-3)` per
   architect plan §"Items I am deferring" and brief §8 explicit
   non-goal.
4. **Protected-route Clerk session for verifier (carryover)** — pass-1
   verification flagged this; pass-2 inherits it. The verification loop
   has now run multiple passes without ever actually rendering
   `/dashboard`, `/opportunities`, or `/opportunities/[id]` in a
   verifier-controlled browser. A permanent fix (test-user session
   token, Clerk testing-tokens setup, or a dedicated verifier service
   account) would let future verification rounds screenshot protected
   surfaces. Worth scheduling before pass 3.

---

## Audit trail (this iteration)

| Check | Method | Result |
|---|---|---|
| Files diffed against main HEAD | `git diff HEAD --stat` | 6 application files: `lib/api.ts`, `components/ui.tsx`, `components/cyber-posture-card.tsx`, `app/(app)/opportunities/page.tsx`, `app/(app)/opportunities/[id]/page.tsx`, `app/(app)/dashboard/page.tsx` |
| Detail render order | `Read [id]/page.tsx:220-357` | PageHeader → meta → `<HighMoatStrip>` → two-column main → "Take action" wrapping the three panels → score breakdown ✓ |
| HighMoat gating | `Read [id]/page.tsx:509-512` | `score.high_moat && score.high_moat.score >= 70` ✓ |
| `HighMoatBlock` type | `Read lib/api.ts:276-298` | 8 fields present; `ScoreBlock.high_moat: HighMoatBlock \| null` ✓ |
| Perspective founder filter | `Read opportunities/page.tsx:94-96` | `s.owner_founder_slug === mySlug \|\| s.owner_founder_slug === null` ✓ |
| Brief tabs use `?view` | `grep view=brief opportunities/[id]/page.tsx` | lines 1056–1057 ✓ |
| Violet color grep | `grep -E "text-violet\|bg-violet" [id]/page.tsx` | 0 hits ✓ |
| KPI grid 4→3 | `Read dashboard/page.tsx:274` | `md:grid-cols-3` ✓ |
| "Sweet spots today" tone | `Read dashboard/page.tsx:283-290` | `tone={value > 0 ? "high_moat" : "neutral"}` ✓ |
| Kpi tone="high_moat" routes to token | `Read ui.tsx:150-156` | `high_moat: "text-[hsl(var(--high-moat))]"` ✓ |
| CyberFitCard rename | `Read cyber-posture-card.tsx:17,26,249` | Symbol renamed; visible title updated; back-compat alias present ✓ |
| Missing clauses surface | `Read cyber-posture-card.tsx:222-240` | `if (clauses.length === 0) return null;` ✓ |
| "Open detail →" removed | `grep "Open detail" dashboard/page.tsx` | only the pass-2 explanation comment at lines 504-506 ✓ |
| Hover swap | `grep "hover:shadow\|hover:bg-accent" dashboard/page.tsx opportunities/page.tsx` | no `hover:shadow` on row classes; `hover:bg-accent/40` on both surfaces ✓ |
| Token unchanged | `git diff HEAD -- apps/web/app/globals.css` | 0 lines ✓ |
| Pass-1 surfaces untouched | `git diff HEAD -- todays-moves.tsx globals.css score.py` | 0 lines ✓ |
| Emoji audit | `git diff` filtered through `[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]` | 0 hits ✓ |
| Hex literal audit | `git diff` filtered through `#[0-9A-Fa-f]{3,8}` on added lines | 0 hits ✓ |
| `console.log` / undated `TODO` / `: any` audit | grep on added lines | 0 hits ✓ |
| typecheck | `cd apps/web && npx tsc --noEmit` | exit 0 ✓ |
| build | `cd apps/web && npx next build` | exit 0; 35 routes compiled ✓ |
| Protected-route render | `curl http://localhost:3000/{dashboard,opportunities}` | 500 (`apiFetch called without a Clerk session`); environment limitation per user instruction, NOT a SHIP blocker ✓ |
