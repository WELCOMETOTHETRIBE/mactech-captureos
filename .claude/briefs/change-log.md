# Change Log
For brief: 2026-05-25T11:36:30-07:00
Iteration: 1 (pass 2 of overall UX program)
Generated: 2026-05-25T12:35:00-07:00

## Items addressed

### Item 1 — Detail-page restructure + "Why this is high-moat" strip
- **Brief reference:** §7.1 (the headline leverage point — pre-decision
  evidence was buried under three post-decision panels; high-moat
  metadata was computed by the backend but absent from the detail UI).
- **Files modified:**
  - `apps/web/lib/api.ts` — added `HighMoatBlock` type with all 8
    fields the API returns (`score`, `breakdown`,
    `is_high_probability_easy_win`, `clause_hits`, `clearance_hits`,
    `role_hits`, `top_clearance`, `why_it_matters_seed`). Extended
    `ScoreBlock` with `high_moat: HighMoatBlock | null`.
  - `apps/web/app/(app)/opportunities/[id]/page.tsx` — new render
    order: PageHeader → meta strip → `<HighMoatStrip>` (conditional)
    → two-column main (brief left, cyber-fit + incumbent + capability
    right) → "Take action on this opportunity" section wrapping
    PursuitPanel + DrafterPanel + AskPanel as three siblings (all
    expanded per §11 Q5) → score breakdown.
- **Files created:** none. `<HighMoatStrip>` is inline in the detail
  page file alongside the other page-local helpers (`Row`, `Meta`,
  `PursuitPanel`, etc.).
- **Approach taken:** Pure render-order rearrangement plus one new
  inline component. PursuitPanel / DrafterPanel / AskPanel internals
  are untouched — only their position relative to the brief / cyber /
  incumbent evidence changes. `<HighMoatStrip>` is gated to
  `score.high_moat && score.high_moat.score >= 70` per §11 Q1; when
  the gate fails the section is absent (not present-but-empty).
  Visual contract: 3px gold left border (`border-l-[3px]
  border-l-[hsl(var(--high-moat))]`), white card background, no gold
  fill or tint anywhere. The `why_it_matters_seed` renders in
  italic-serif to echo the page H1. Right half is a 3-column meta
  grid surfacing `clause_hits`, `top_clearance` (when `!= "NONE"`),
  `role_hits` — each clause and role wrapped in `<ExplainLink>` so a
  layman can click into a plain-English explanation. An `<HpewBadge
  size="sm">` sits beside the eyebrow when
  `is_high_probability_easy_win`.
- **Design decisions worth flagging:**
  - **The `HpewBadge` primitive grew a `size` prop earlier; we use
    `size="sm"` inside the strip** so the chip doesn't visually
    compete with the H1 / score badge above it. The full-size chip
    keeps living on list and dashboard rows.
  - **`why_it_matters_seed` may be null** even when
    `high_moat.score >= 70` — the strip still renders, falling back
    to a calm "the high-moat scorer flagged this opp but didn't emit
    a one-sentence rationale; open the score breakdown below" line.
    Never errors, never empty.
  - **Three-column right grid** uses `dl` semantics (`<dt>` label, `<dd>`
    badge group). Reads cleanly with a screen reader and avoids
    "cards inside a card" visual noise.
- **What I did NOT do and why:**
  - I did NOT promote the high-moat strip to its own page
    (`/opportunities/{id}/high-moat`) — brief §8 explicit non-goal.
  - I did NOT touch the `HpewBadge` primitive's chip-row appearance
    on list / dashboard rows — pass-1 surface, off-limits.

### Item 2 — Perspective left-rail on /opportunities
- **Brief reference:** §7.2.
- **Files modified:**
  - `apps/web/app/(app)/opportunities/page.tsx` — added `?saved_search`
    to the `SP` type. Fetches `/me` + `/me/settings` alongside the
    existing `/opportunities` call. Filters
    `settings.saved_searches` to `owner_founder_slug === me.founder.slug
    || owner_founder_slug === null` (founder-private + tenant-shared).
    Resolves `?saved_search=<id>` to a `SavedSearchOut`; if the id is
    unknown or belongs to a different founder, silently falls through
    to "All opportunities" (never errors). Replaced the old facet
    aside contents with `<PerspectiveRail>` on top + a "Refine this
    view" `<details>` drawer wrapping the facet filters underneath.
    The drawer is `open` by default only when no perspective is
    active.
- **Files created:** none. `<PerspectiveRail>` and
  `<PerspectiveRailItem>` are inline in the same file.
- **Approach taken:** Pure server-side composition (brief §7.2 Option
  A). The perspective seeds the backend params: `assigned_founder` =
  the search's `owner_founder_slug`; `score_min` = the search's
  `alert_threshold`. For the seeded "Patrick — UFGS 25 / FRCS Cyber"
  high-moat search, the composition additionally sets
  `sweet_spot_only=true`, `sort=high_moat_desc`, and
  `high_moat_min=<alert_threshold>`. High-moat detection key: the
  search name or its keyword list matches
  `\b(UFGS|FRCS|UMCS|HIGH[-\s]?MOAT)\b` (case-insensitive). No API
  schema change — the existing `/opportunities` endpoint already
  accepts all the relevant params (verified at
  `routes/opportunities.py` line 230+).
- **Design decisions worth flagging:**
  - **Perspective seeds, doesn't lock.** Any explicit URL param
    (`?score_min=80`, `?assigned_founder=james-adams`) wins over the
    perspective's seeded value. Lets the user drill into a
    perspective without losing the rail's affordances.
  - **Empty perspective list renders "All opportunities" only**
    (brief §11 Q3). No inline CTA pointing at /settings. The settings
    page already owns the saved-search admin surface.
  - **Active state uses the same `border-l-2 border-primary
    bg-primary/10` treatment `SidebarNav` uses** for the primary nav,
    so the visual language reads as "same kind of left rail."
  - **Subtitle changes when a perspective is active**: "Perspective:
    <name> — showing N–M of T opportunities." Surfaces the active
    perspective at the page header so the user always knows where
    they are.
- **What I did NOT do and why:**
  - I did NOT add a `saved_search: str` query param on the backend
    (brief §7.2 explicitly recommended Option A over Option B).
  - I did NOT add a Cmd-K shortcut to swap perspectives — brief §8
    no-new-keyboard-shortcuts non-goal.

### Item 3 — Brief tab affordance + BriefList token discipline
- **Brief reference:** §7.3.
- **Files modified:**
  - `apps/web/app/(app)/opportunities/[id]/page.tsx`:
    - `searchParams` Promise extended with `view?: string`. Sanitized
      to `"brief" | "raw" | null`; any other value falls through to
      the default (brief when a brief row exists, raw otherwise).
    - Replaced anchor-tabs (`#brief-{id}` / `#raw-{id}`) with `<Link
      href="?view=brief">` and `<Link href="?view=raw">` tabs. Active
      tab gets `bg-primary text-primary-foreground` (matches the
      score-bucket pills); inactive gets `border border-border
      text-foreground hover:border-foreground/40`. Both tabs use
      `scroll={false}` to keep the user's vertical position.
    - Inside the panel, only the active panel renders (the `:target`
      trick is gone). `aria-selected` reflects which tab is active.
    - "Regenerate brief" affordance moved from the tab header right
      side to the brief panel's footer, sitting next to the
      "Auto-generated by …" provenance line.
    - `BriefList`'s `violet` tone routes to `text-muted-foreground`
      (label) and `bg-muted-foreground` (dot) per §11 Q2 — neutral,
      not pillar-coded.
- **Files created:** none.
- **Approach taken:** Search-param tabs are server-component-friendly
  with no client state. Each tab is a `<Link>` that points at
  `?view=brief` or `?view=raw` — the parent route's
  `force-dynamic` directive means each click round-trips the server
  and re-renders. Verified
  `grep -E "text-violet|bg-violet" apps/web/app/\(app\)/opportunities/\[id\]/page.tsx`
  returns zero hits (success criterion §9).
- **Design decisions worth flagging:**
  - **Tab visual matches the score-bucket pills on the list page.**
    Consistent segmented-control language across the app.
  - **Default behavior is asymmetric** — when there's no brief row,
    the raw tab is default; when there is a brief row, the brief tab
    is default. Gives the user something to read on arrival in both
    states.
  - **`scroll={false}`** on the tab links so flipping tabs doesn't
    jump the page back to the top of the brief panel. Stays where
    you were reading.
  - **Did NOT add a "Copy brief to clipboard" affordance** — the
    brief floated this as optional polish; adding it requires a
    client island (the rest of the panel is server-rendered) and
    would have grown the diff for marginal value. Easy follow-up.
- **What I did NOT do and why:**
  - I did NOT add `?view=brief|raw` on the list page — brief §8
    explicit non-goal.
  - I did NOT pillar-code the BriefList violet tone — brief §11 Q2
    chose the neutral path explicitly.

### Item 4 — KPI strip 4 → 3 tiles, "Sweet spots today" leading
- **Brief reference:** §7.4.
- **Files modified:**
  - `apps/web/app/(app)/dashboard/page.tsx` — KPI grid changed from
    `md:grid-cols-4` to `md:grid-cols-3`. First tile is now "Sweet
    spots today" (value = `kpis.your_sweet_spots_open`, hint =
    "high-probability easy wins in your lane, not yet in pipeline",
    href = `/opportunities?sweet_spot_only=true&sort=high_moat_desc&assigned_founder={slug}`,
    tone = `"high_moat"` when value > 0 else `"neutral"`). Tile
    always renders even at 0 — zero is signal too on a triage
    dashboard. "High-fit untracked" + "Deadlines this week" stay
    (slots 2 and 3). "Active pursuits" + "Drafts to review" moved
    into a single text line under TodaysMoves — "Your work: N active
    pursuits · M drafts to review." Each segment is a Link.
  - `apps/web/components/ui.tsx` — extended `Kpi`'s `tone` union to
    include `"high_moat"`. The high-moat tone routes the value text
    through `text-[hsl(var(--high-moat))]`; the hint stays
    `text-muted-foreground`. When count === 0, callers pass
    `tone="neutral"` so the tile reads as a calm zero, not a
    gold-tinted alarm.
  - `apps/web/app/(app)/dashboard/page.tsx` — KPI glossary line under
    the strip refreshed: "sweet spot · high-fit · pipeline · score"
    (was "high-fit · pipeline · draft · score"). The glossary still
    routes each term through `<TermPopover>`.
- **Files created:** none.
- **Approach taken:** Tile reorder + one new tone branch. The "Your
  work" line is a small text strip with two text links sitting
  directly under `<TodaysMoves>`. Loses no information — both numbers
  are still visible above-fold — and recovers vertical rhythm for
  the higher-signal three tiles.
- **Design decisions worth flagging:**
  - **`tone="high_moat"` never auto-degrades inside the Kpi
    primitive.** Callers pass `tone="neutral"` explicitly when the
    count is 0. Gravitas is the caller's call, not the primitive's
    default.
  - **Sweet-spots tile renders even at 0** — zero is signal on a
    triage dashboard. Brief §7.4: "render even when 0 — zero is
    signal too, but skip the gold tone when the value is 0."
  - **"Your work" demote uses tabular-nums on the inline numbers** so
    the line scans like a sub-counter, not a sentence.
- **What I did NOT do and why:**
  - I did NOT change the `<TodaysMoves>` order — pass-1 surface,
    off-limits.
  - I did NOT add a separate "Your work" card with its own border —
    the brief specified a single text line.

### Item 5 — CyberFitCard rename + "What's missing" rail + row-hover polish
- **Brief reference:** §7.5.
- **Files modified:**
  - `apps/web/components/cyber-posture-card.tsx`:
    - Exported symbol renamed from `CyberPostureCard` → `CyberFitCard`.
      Visible card title changed from "Cyber posture vs. solicitation"
      to "Cyber fit · your posture vs. their ask".
    - Back-compat alias `export const CyberPostureCard = CyberFitCard`
      added at the bottom of the file so any external imports
      (internal or otherwise) still resolve during the transition.
    - File path stays at `cyber-posture-card.tsx` (§11 Q4).
    - New `<MissingClausesRail>` component renders under the
      sufficiency banner when `summary.missing_clauses?.length > 0`.
      Backend currently returns the field absent — the rail renders
      nothing on day one. The day the backend cross-reference logic
      ships, the surface lights up with no further UI work.
  - `apps/web/lib/api.ts` — added optional `missing_clauses?:
    string[]` to `CyberSummaryOut`. Optional so the type is
    back-compat with the current backend response (which doesn't yet
    include the field).
  - `apps/web/app/(app)/opportunities/[id]/page.tsx` — import +
    JSX call site updated from `CyberPostureCard` to `CyberFitCard`.
  - `apps/web/app/(app)/dashboard/page.tsx` — dropped the explicit
    `<p>Open detail →</p>` line at the bottom of each "Your top" row.
    Swapped `hover:shadow-sm` for `hover:bg-accent/40` on the
    non-sweet-spot row class. Same hover swap on the sweet-spot
    variant (still keeps the gold left border on hover).
  - `apps/web/app/(app)/opportunities/page.tsx` — same hover swap on
    the list rows: `hover:shadow-sm` → `hover:bg-accent/40` for both
    sweet-spot and standard variants.
- **Files created:** none.
- **Approach taken:** Single-symbol rename across two files. The
  back-compat alias is a defensive guard — there are no current
  external consumers of `CyberPostureCard` per a repo-wide grep, but
  the alias costs one line and removes the bisect risk on any merge
  conflict during a long-lived branch.
- **Design decisions worth flagging:**
  - **"What's missing" rail uses `text-warning` for the label, not
    `text-destructive`.** Per brief §7.5: "this is a 'to-do' list,
    not a panic surface." The warning tone matches the gap-state
    sufficiency banner without escalating.
  - **`MissingClausesRail` renders absolutely nothing when the list
    is empty** (early `return null`) — not a hidden surface, just
    not in the tree. The backend can ship the field at any later
    date with zero front-end follow-up required.
  - **`TODO(pass-3)` comment** placed inline at the rail's mounting
    point in `cyber-posture-card.tsx` so the next agent / human can
    grep for it and know the cross-reference endpoint is the
    remaining work.
  - **Row-hover swap matches both surfaces** — sweet-spot and
    non-sweet-spot rows on both /dashboard and /opportunities lose
    the soft shadow lift in favor of a subtle background tint.
    Calmer leaderboard posture (brief §6 motion guidance).
- **What I did NOT do and why:**
  - I did NOT rename the file path (`cyber-posture-card.tsx` stays) —
    brief §11 Q4 explicit decision.
  - I did NOT add the backend cross-reference logic for
    `missing_clauses` — brief §8 explicit non-goal; tracked as
    `TODO(pass-3)`.

## New primitives introduced

None. Every change in this pass is either a render-order rearrangement,
a search-param-driven UI swap, an inline single-use composition, or an
extension of an existing primitive's `tone` union.

Specifically:
- `<HighMoatStrip>` is inline in `opportunities/[id]/page.tsx` — single
  call site, no shared primitive warranted.
- `<PerspectiveRail>` / `<PerspectiveRailItem>` are inline in
  `opportunities/page.tsx` — same reason.
- `<MissingClausesRail>` is inline in `cyber-posture-card.tsx`.
- `Kpi`'s `tone` union grew a `"high_moat"` member — same primitive,
  one more variant.

## Tokens / config changed

None. The `--high-moat` token value (`45 90% 28%`) is locked from pass
1's iteration-3 final and is NOT touched this pass (brief §8 explicit
non-goal).

## Test commands run and their result
- typecheck: **PASS** (`cd apps/web && npx tsc --noEmit` → exit 0,
  no output).
- lint: NOT RUN (same pre-existing `next lint` tooling glitch from
  pass 1 — "Invalid project directory provided, no such directory:
  …/apps/web/lint." Unrelated to this pass).
- build: **PASS** (`cd apps/web && npx next build` → exit 0, all 35
  routes compiled; same route count as pass 1).
- Python AST: NOT RUN — no Python touched this pass (all changes
  client-side except for type-only extensions in `lib/api.ts`).
- Visual diff: NOT RUN (protected-route verification gap from
  pass-1 iteration 2 unchanged — verifier has no Clerk session).

## Known limitations

1. **Visual confirmation on protected routes still pending.** Same
   carry-over from pass 1: `/dashboard`, `/opportunities`,
   `/opportunities/[id]` can't be screenshot-verified in the verifier
   environment without a Clerk session. The changes in this pass are
   architectural enough that a logged-in eyeball pass from at least
   one of the four founders should land before SHIP — especially:
   - the new render order on the detail page (does the bid/no-bid
     triage feel right above the fold? does the "Take action" rail
     feel like one bundle or three random panels?);
   - the gold "Why this is high-moat" strip on a real high-moat opp
     (does the gold rail read as embossed-seal gold against the
     warm-paper background?);
   - the perspective rail on /opportunities for Patrick (does the
     UFGS / FRCS Cyber perspective actually surface the high-moat
     opps without an empty result set?).
2. **"What's missing" rail is UI-only this pass.** The backend
   doesn't yet emit `missing_clauses` on `/opportunities/{id}/cyber-summary`.
   The rail renders nothing on day one. The cross-reference logic
   (cited clauses minus tenant evidence) is a `TODO(pass-3)`
   endpoint addition — see brief §8 explicit non-goal and inline
   code comment in `cyber-posture-card.tsx`.
3. **High-moat strip relies on `score_one_sentence`-style content
   in `why_it_matters_seed`.** If the worker chain doesn't populate
   this field for some legacy opps, the strip falls back to a
   neutral message rather than rendering empty. The fallback is
   verified in code but not yet verified visually.
4. **Perspective rail does not yet show a count or last-delivered
   timestamp** per saved search. The settings page already surfaces
   these on the admin cards; the rail kept its body small to honor
   the "calm chrome" direction. Easy follow-up if the founders ask.
5. **Brief tab `?view=brief|raw` resets on hard navigation back to
   `/opportunities`.** No persistence across opp clicks. This is
   intentional — the tab is a per-opp preference, not a per-user
   global. If we want sticky behavior, the next pass could persist
   to a cookie or `localStorage`.
6. **Perspective rail's `assigned_founder` seed forces the active
   founder filter.** A founder browsing another lane's perspective
   (e.g., John viewing James's "Infrastructure daily") will land
   filtered to `@james-adams` automatically. This is the desired
   behavior — the perspective IS the founder's lane — but it means
   "switch perspectives" feels different from "clear filters."
   Documented in code; not a defect.
7. **Pre-existing CyberPostureCard back-compat alias** is exported.
   No current consumers exist in the repo per grep; the alias is a
   defensive guard against in-flight branches that may still import
   the old name. Plan to remove in a future pass once we've audited
   external apps.
8. **All pass-1 known limitations still apply.** Backfill of
   `scope_one_sentence` is still lazy; the keyboard `g+s` shortcut
   to the sweet-spots toggle still isn't bound; the
   `opportunities/page.tsx` shell still uses legacy
   `border-neutral-200` / `bg-white` (out of scope this pass —
   migrating the whole shell is a separate cleanup).

## Suggested verifier focus

1. **High-moat strip gate.** Verify the strip renders ONLY when
   `score.high_moat && score.high_moat.score >= 70`. On a non-high-moat
   opp (or one with `high_moat.score === null`), the strip is absent
   from the DOM — not present-but-hidden. Confirm via `View Source` on
   one of each.
2. **Detail-page render order on first scroll.** On a 1440×900
   viewport at the top of the page, the visible tree should be:
   PageHeader → meta strip → (high-moat strip if gated open) → brief
   panel (or first half of two-column main). PursuitPanel +
   DrafterPanel + AskPanel must NOT be above the fold. The
   "Take action" eyebrow should be visible before the score
   breakdown when you scroll down past the two-column main.
3. **`grep -E "text-violet|bg-violet"
   apps/web/app/\(app\)/opportunities/\[id\]/page.tsx` returns 0
   hits.** Confirmed during build verification — re-run to confirm
   no regression.
4. **Brief tab visual diff.** Open a detail page with a brief and
   click "Plain-English brief" vs. "Original SAM text" — the active
   tab should fill with `bg-primary text-primary-foreground`; the
   inactive should be `border border-border`. Verify the URL changes
   to `?view=brief` / `?view=raw` accordingly. Verify the
   "Regenerate brief" button is in the brief-panel footer next to
   the provenance line, NOT in the tab header.
5. **Perspective rail filtering.** Log in as Patrick — the rail
   should show "All opportunities" + Patrick's two saved searches
   (Security daily + UFGS / FRCS Cyber). Log in as Brian — the rail
   should show "All opportunities" + Brian's Quality daily only. No
   other founder's saved searches should appear in any user's rail.
6. **UFGS perspective behavior.** Click "Patrick — UFGS 25 / FRCS
   Cyber" — the resulting URL should be
   `/opportunities?saved_search=<id>`; the internal API call to
   `/opportunities` should carry `sweet_spot_only=true`,
   `sort=high_moat_desc`, `high_moat_min=80`,
   `assigned_founder=patrick-caruso`, `score_min=80`. Verify by
   network-tab inspection.
7. **KPI strip render at 0.** Open the dashboard when
   `your_sweet_spots_open === 0` — the tile should render with a
   neutral foreground value (not gold). When the value > 0, the value
   text should be gold-inked.
8. **`CyberFitCard` rename.** Search the rendered HTML for "Cyber fit"
   on a detail page — must find the new title "Cyber fit · your
   posture vs. their ask." Old title "Cyber posture vs. solicitation"
   should not appear.
9. **Row hover.** Hover over a `/dashboard` "Your top" row and an
   `/opportunities` list row — both should show a subtle
   `bg-accent/40` background tint, not a soft `shadow-sm` lift.
   Sweet-spot rows should still keep the gold left border on hover.
10. **No "Open detail →" line on dashboard rows.** Inspect any
    /dashboard "Your top" row in the rendered HTML — no
    `<p className="... text-primary">Open detail →</p>` should appear
    inside the row's `<Link>`.
11. **Contrast preserved.** The `--high-moat` token is unchanged
    (`45 90% 28%` from pass-1 iter 3 — measured 4.97:1 on paper-50
    and 5.24:1 on white). New callsites in this pass that use the
    token:
    - `<HighMoatStrip>` eyebrow text (`text-[hsl(var(--high-moat))]`
      on white card)
    - `<HighMoatStrip>` 3px left rail (`border-l-[hsl(var(--high-moat))]`)
    - `<Kpi tone="high_moat">` value text
      (`text-[hsl(var(--high-moat))]` on white card)
    All inherit the same WCAG measurements as pass-1 callsites.
12. **`tsc --noEmit` and `next build` both exit 0** — confirmed
    locally; verifier should re-confirm.
