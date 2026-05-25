# Architect Plan
For brief: 2026-05-25T11:36:30-07:00
Iteration: 1 (pass 2 of overall UX program; pass-1 plan snapshotted)

## Items I will address this pass

All five leverage points from §7 of the pass-2 brief. They are independent
enough to ship in one diff and small enough that consolidating them avoids
the rebase churn of staging across two passes. Section 11 of the brief
gave explicit human decisions on the open questions; this plan honors
each one exactly.

1. §7.1 — Restructure opportunity-detail render order around bid/no-bid
   AND add the "Why this is high-moat" strip (gated `score.high_moat &&
   score.high_moat.score >= 70` per §11 Q1).
2. §7.2 — Perspective left-rail on /opportunities. Founder-private filter
   `owner_founder_slug == me.founder.slug || owner_founder_slug == null`.
   Empty rail renders "All opportunities" only (per §11 Q3 — no CTA).
3. §7.3 — Brief / Raw tab affordance moves from anchor-`:target` to a
   real `?view=brief|raw` search param. BriefList `violet` tone routes
   to `text-muted-foreground` (per §11 Q2 — neutral, not pillar-coded).
   Regenerate-brief affordance moves into the brief panel footer next to
   the provenance line.
4. §7.4 — KPI strip from 4 to 3 tiles. "Sweet spots today" leads (gold
   ink only when count > 0; neutral when 0 — gravitas, not crying wolf).
   "High-fit untracked" stays slot 2. "Deadlines ≤7d" stays slot 3.
   "Active pursuits" + "Drafts to review" demoted to a single text line
   under TodaysMoves ("Your work: N active pursuits · M drafts to review").
5. §7.5 — `CyberPostureCard` → exported symbol renamed to `CyberFitCard`
   with visible title "Cyber fit · your posture vs. their ask". File
   path stays `components/cyber-posture-card.tsx` (per §11 Q4). "What's
   missing" sub-rail surface added — renders only when
   `summary.missing_clauses?.length > 0` (backend returns empty list
   for now; the cross-reference logic is a pass-3 backend addition,
   marked as TODO). Drop the "Open detail →" verbal CTA on dashboard
   "Your top" rows. Both dashboard + opportunities rows swap
   `hover:shadow-sm` for `hover:bg-accent/40`.

## For each item

### 1. Detail-page restructure + high-moat strip (brief §7.1)

- **Files I will touch:**
  - `apps/web/lib/api.ts` — add `HighMoatBlock` type with all 8 fields
    the API returns (`score`, `breakdown`, `is_high_probability_easy_win`,
    `clause_hits`, `clearance_hits`, `role_hits`, `top_clearance`,
    `why_it_matters_seed`). Extend `ScoreBlock` with
    `high_moat: HighMoatBlock | null` (the API already returns this —
    types just need to catch up, per brief §7.1 evidence).
  - `apps/web/app/(app)/opportunities/[id]/page.tsx` — new render order:
    PageHeader → meta strip → `<HighMoatStrip>` (conditional) →
    two-column main (brief left, cyber/incumbent/cap right) → "Take
    action on this opportunity" section header wrapping PursuitPanel +
    DrafterPanel + AskPanel as three siblings (per §11 Q5 — no
    accordion, all three expanded) → score breakdown.
  - New inline component `<HighMoatStrip>` rendered when
    `score.high_moat && score.high_moat.score >= 70`. Composition:
    same `rounded-md border border-border bg-card p-5` chrome as the
    meta strip, plus a 3px gold left border
    (`border-l-[3px] border-l-[hsl(var(--high-moat))]`). Inside: a
    small `<HpewBadge>` in the top-left when
    `is_high_probability_easy_win`. Left half is `why_it_matters_seed`
    (15px leading-snug italic-serif to echo the page H1). Right half
    is a 3-column meta grid: "Clauses cited" (clause_hits as neutral
    Badges wrapped in ExplainLink for `clause:UFGS 25 05 11` etc.),
    "Top clearance" (top_clearance value, only if `!= "NONE"`),
    "Cleared roles needed" (role_hits as neutral Badges wrapped in
    ExplainLink for `role:ISSM` etc.). No gold fill, no gold tint
    background — left-border + ink only, matching the pass-1 token
    contract.

- **Approach:** All render-order changes happen inside the same
  `<div className="min-w-0 space-y-6">` wrapper that already exists.
  PursuitPanel / DrafterPanel / AskPanel internals stay untouched —
  only their position changes. The "Take action" wrapper is a single
  `<section>` with a quiet `text-xs uppercase tracking-wider
  text-muted-foreground` eyebrow + `border-t border-border pt-6` to
  read as one bundle.

- **New primitives I will create:** `<HighMoatStrip>` and the
  "Take action" section wrapper live inline in `[id]/page.tsx` — both
  are single-use compositions of existing primitives (`HpewBadge`,
  `Badge`, `ExplainLink`, `AnnotatedProse`). No new shared primitive
  warranted.

- **Risk of regression:** Medium. The PursuitPanel / DrafterPanel /
  AskPanel are large existing components; moving them is the
  highest-blast-radius change in this pass. Mitigation: their
  internals don't change, only their wrapping `<section>` and order.
  Build verifies render.

### 2. Perspective left-rail on /opportunities (brief §7.2)

- **Files I will touch:**
  - `apps/web/app/(app)/opportunities/page.tsx` — replace the existing
    `<aside>` filter sidebar contents with a two-section rail:
    TOP — "Perspectives" list (All opportunities + founder-private
    saved searches). BOTTOM — "Refine this view" collapsible
    `<details>` wrapping the existing facet filters (set-aside /
    notice-type / assigned-founder + the nested NAICS / sort under
    "More filters"). `<details open>` only when no perspective is
    active (i.e., `sp.saved_search` is unset).
  - Server-side composition for `?saved_search={id}`: the page
    component fetches `/me/settings` alongside the existing
    `/opportunities` fetch, looks up the saved search by id (filtered
    by `owner_founder_slug == me.founder.slug || owner_founder_slug
    == null`), and translates its filters into the existing query
    params: `assigned_founder=<owner_slug>`,
    `score_min=<alert_threshold>`. For the seeded high-moat saved
    search ("Patrick — UFGS 25 / FRCS Cyber"), the composition
    additionally sets `sweet_spot_only=true`, `sort=high_moat_desc`,
    `high_moat_min=<alert_threshold>`. The high-moat detection key:
    search name contains "UFGS" or "FRCS" or "high-moat"
    (case-insensitive). This is the minimal-cost heuristic that doesn't
    require an API schema change.

- **Approach:** Pure URL-driven (no client state). The active
  perspective is highlighted via the same
  `border-l-2 border-primary bg-primary/10` pattern `SidebarNav`
  already uses. The page subtitle changes to reflect the active
  perspective ("Perspective: <name>") above the score-bucket strip.

- **New primitives I will create:** Inline `<PerspectiveRail>` and
  `<PerspectiveRailItem>` components in `opportunities/page.tsx`.
  Single-use; doesn't earn a shared primitive.

- **Risk of regression:** Low-medium. The aside contents are replaced
  but the facet filters still render (just collapsed under "Refine
  this view"). All existing URL params still resolve. The new
  composition runs server-side at request time — no client work, no
  RSC boundary changes.

### 3. Brief tab affordance + BriefList token discipline (brief §7.3)

- **Files I will touch:**
  - `apps/web/app/(app)/opportunities/[id]/page.tsx`:
    - Replace anchor-tabs (`#brief-{id}` / `#raw-{id}`) with
      `?view=brief|raw` search-param tabs. Active tab gets
      `bg-primary text-primary-foreground` (matches the score-bucket
      pills); inactive gets `border border-border text-foreground
      hover:border-foreground/40`. Default: `brief` when a brief row
      exists, `raw` when null.
    - The `searchParams` Promise grows `view?: "brief" | "raw"`.
    - Inside `<BriefAndDescriptionPanel>`, only the active panel
      renders — the `:target` trick goes away.
    - "Regenerate brief" moves from the tab-header right side to the
      brief-panel footer, sitting next to the `Auto-generated by …`
      provenance line.
    - `BriefList`'s `violet` tone resolves to `text-muted-foreground`
      (label) and `bg-muted-foreground` (dot). The other three tones
      (`brand`, `neutral`, `amber`) stay routed through their existing
      tokens.

- **Approach:** Search-param tabs are server-component-friendly with
  no client state. Each tab is a `<Link>` that copies the existing
  search params (including `explain` and `saved_search`) and sets
  `view`. Hover/active classNames mirror the score-bucket pills on
  the list page so the visual language reads as "same kind of
  segmented control."

- **New primitives I will create:** None — both changes are local
  refactors inside the existing panel function.

- **Risk of regression:** Low. The router/route shape doesn't change.
  Only the inner JSX of `<BriefAndDescriptionPanel>` and the
  `BriefList` className map.

### 4. KPI strip 4 → 3 + "Sweet spots today" leading (brief §7.4)

- **Files I will touch:**
  - `apps/web/app/(app)/dashboard/page.tsx` — KPI grid changes from
    `md:grid-cols-4` to `md:grid-cols-3`. First tile becomes "Sweet
    spots today" (value = `kpis.your_sweet_spots_open`, hint =
    "high-probability easy wins in your lane, not yet in pipeline",
    href =
    `/opportunities?sweet_spot_only=true&sort=high_moat_desc&assigned_founder={slug}`,
    tone = `"high_moat"` when value > 0 else `"neutral"`). Tile
    renders even at 0 — zero is signal too on a triage dashboard.
    "High-fit untracked" + "Deadlines this week" stay (slots 2 and 3).
    Active pursuits + Drafts to review move into a one-line "Your
    work" rail under TodaysMoves.
  - `apps/web/components/ui.tsx` — extend the `Kpi` component's `tone`
    union to include `"high_moat"`. The high-moat tone routes
    `text-[hsl(var(--high-moat))]` for the value text; hint label
    stays muted-foreground. When count === 0, callers pass
    `tone="neutral"` (the high-moat tone never auto-degrades inside
    the primitive — gravitas is the caller's call).

- **Approach:** Tile reorder + one new tone branch. The demoted "Your
  work" line is a small text strip with two text links, sitting
  directly under the `<TodaysMoves>` block.

- **New primitives I will create:** None — extending an existing
  primitive's `tone` union, not adding a new one.

- **Risk of regression:** Low. The Kpi visual shape doesn't change;
  only one new tone branch is added. The strip grid change from 4 to
  3 columns is a Tailwind class swap.

### 5. CyberFitCard rename + What's missing rail + dashboard row polish (brief §7.5)

- **Files I will touch:**
  - `apps/web/components/cyber-posture-card.tsx` — rename exported
    symbol from `CyberPostureCard` → `CyberFitCard`. Visible card
    title changes from "Cyber posture vs. solicitation" to "Cyber fit
    · your posture vs. their ask". File path stays the same (per
    §11 Q4). Add an optional "What's missing" sub-rail under the
    sufficiency banner that renders only when
    `summary.missing_clauses?.length > 0`. List label uses
    `text-warning`; each clause is a neutral Badge wrapped in
    ExplainLink to `clause:{name}`. Backend currently returns an
    empty list; the surface lights up the day the API ships the
    cross-reference. Mark with a `TODO(pass-3)` code comment.
  - `apps/web/lib/api.ts` — add `missing_clauses?: string[]` to
    `CyberSummaryOut`. Optional so the field is back-compat with the
    current backend response (which doesn't include it).
  - `apps/web/app/(app)/opportunities/[id]/page.tsx` — update the
    import + JSX from `CyberPostureCard` to `CyberFitCard`.
  - `apps/web/app/(app)/dashboard/page.tsx` — drop the `<p>Open detail
    →</p>` line at the bottom of each "Your top" row (lines 478–480).
    Swap `hover:shadow-sm` → `hover:bg-accent/40` on the non-sweet-spot
    row class.
  - `apps/web/app/(app)/opportunities/page.tsx` — same hover swap on
    the non-sweet-spot row class (`hover:shadow-sm` →
    `hover:bg-accent/40`).

- **Approach:** Single-symbol rename across two files (component +
  one consumer). The "What's missing" rail is purely additive UI;
  backend returns empty for now so the surface only renders when
  populated.

- **New primitives I will create:** None — the rail surface is inline
  in `cyber-posture-card.tsx` and is single-use.

- **Risk of regression:** Low. The rename is purely internal — no
  routing change, no API change. The rail's empty-state is "render
  nothing," so the day-1 visual diff is zero on the cyber card
  itself. Hover swap is a className change on two files. The "Open
  detail →" drop is removing a paragraph — every row was already a
  clickable `<Link>`, so functionality is preserved.

## Items I am deferring this pass

- **Backend cross-reference logic for "What's missing"** — per brief
  §8 explicit non-goal. The UI surface ships now; the backend
  cross-reference (SPRS-vs-clauses gap detector) is a TODO(pass-3)
  endpoint addition. Marked in code with a dated TODO.
- **`g+s` keyboard shortcut to the Sweet-spots toggle** — pass-1
  change log noted this as a natural follow-up; brief §8 says don't
  add new global shortcuts this pass. Honored.
- **Backfill of `scope_one_sentence`** — pass-1 known limitation;
  lazy via re-score. Not in scope.
- **Backend `saved_search: str` API param** — brief §7.2 explicitly
  recommends Option A (server-side composition in the Next page)
  over Option B (API param). Honored.
- **Promote high-moat strip to its own page** — brief §8 explicit
  non-goal. The strip stays inline.
- **Feedback / thumbs widget** — brief §8 explicit non-goal. Phase 2.
- **Dark mode / glass panels / animated KPIs** — brief §8 explicit
  non-goals. Continued from pass 1.
- **Token value re-tuning of `--high-moat`** — brief §8 explicit:
  `45 90% 28%` is locked. Not touching.

## Open disagreements with the brief

None. The brief's §11 human answers fully resolve the open questions:

- Q1 — threshold `score.high_moat.score >= 70` is unambiguous; it's
  what the pass-1 architect plan already used and aligns with the
  "Top fit" score bucket on the list page.
- Q2 — `text-muted-foreground` is the cleaner of the two; the
  pillar-coding alternative would have introduced semantic load the
  layman BD lead has no way to decode without a legend.
- Q3 — "All opportunities only" empty rail is consistent with the
  settings page already owning the saved-search admin surface.
- Q4 — symbol-only rename keeps the diff tight and respects any
  external bookmarks to the file path.
- Q5 — keeping all three Take-action panels expanded matches the
  brief's "no accordion, no extra control surface" direction and
  honors the original §7.1 proposal exactly.
