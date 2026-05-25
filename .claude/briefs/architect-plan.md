# Architect Plan
For brief: 2026-05-25T09:29:00-07:00
Iteration: 1

## Items I will address this pass

Five leverage points from §7, chosen for compounding effect on the daily question
("for me, today, what should I open?"). Brief §11 answers govern: high-moat is
universal across founders; gold token is `45 90% 45%` left-border + corner marker
only (never fill); brief auto-gen at score ≥ 60 lands in the worker chain; saved
searches stay founder-private; NO feedback / thumbs affordance.

1. §7.1 — Wire the high-moat track end-to-end into the discovery UI
2. §7.5 — Add a sweet-spot move to "Today's moves"
3. §7.8 — Sweet-spot row treatment on the opportunities list AND dashboard "Your top"
4. §7.2 — Auto-generate the plain-English brief on every score ≥ 60 and promote
   `scope_one_sentence` to the primary list-row title (worker chain change)
5. §7.7 — Migrate `CyberPostureCard` to the token system (drop the legacy
   `bg-emerald-50` / `bg-red-50` / `bg-amber-50` literals)

These five compose: §7.1 + §7.8 + §7.5 ship the sweet-spot signal across all
three primary discovery surfaces (list / dashboard top / today's moves) with one
consistent gold accent. §7.2 makes every list row scannable in plain English in
the same pass. §7.7 stops the one card that sits inside the new strip from
looking visually off-key against its token-driven neighbors.

## For each item

### 1. High-moat track in the discovery UI (brief §7.1)
- **Files I will touch:**
  - `apps/web/lib/api.ts` — add `high_moat_score` and `is_sweet_spot` to
    `OpportunityListItem` (already exposed by the API; type just needs to
    catch up).
  - `apps/web/tailwind.config.ts` — register the `high-moat` color from the
    new CSS var.
  - `apps/web/app/globals.css` — add `--high-moat: 45 90% 45%` token.
  - `apps/web/components/ui.tsx` — add `<HpewBadge>` primitive (gold pill
    "HPEW"). Universal — not pillar-gated per Q1.
  - `apps/web/app/(app)/opportunities/page.tsx` — add a fourth score-bucket
    pill "Sweet spots" that issues `?sweet_spot_only=true&sort=high_moat_desc`
    via URL params. Apply sweet-spot row treatment (gold left border + HpewBadge).
- **Approach:** Pure URL-driven toggle (no client state). Server reads
  `sp.sweet_spot_only === "true"` and `sp.sort`, forwards them to the API.
  Row treatment is a single conditional className on the `<Link>` plus an
  inline HpewBadge in the chip row.
- **New primitives I will create:** `HpewBadge` in `ui.tsx`. Uses the
  `--high-moat` token via `text-[hsl(var(--high-moat))]` with a thin gold
  border — keeps the token contract intact.
- **Risk of regression:** Minimal — additive on a typed API column. The
  `?sort=high_moat_desc` was already accepted by the backend; the only
  change is exposing it in `SORT_LABELS` so it appears in the More-filters
  drawer too.

### 2. Sweet-spot Move in Today's moves (brief §7.5)
- **Files I will touch:**
  - `apps/api/src/mactech_api/routes/me.py` — add
    `your_sweet_spots_open` int field to `DashboardKpis`. Count is
    "high-fit opps assigned to me where `high_moat_flags.is_high_probability_easy_win`
    = true AND not in pipeline."
  - `apps/web/lib/api.ts` — extend `DashboardKpis` with `your_sweet_spots_open`.
  - `apps/web/components/todays-moves.tsx` — add a new slot-1 Move
    ("Pursue: N sweet-spot…") that uses the gold tone, links to
    `/opportunities?sweet_spot_only=true&assigned_founder={slug}&sort=high_moat_desc`.
  - Extend the existing `Move.tone` field to include `"high_moat"` (gold).
- **Approach:** The Move type currently supports `"amber" | "brand" | "neutral"`.
  Extend to add `"high_moat"`. Render path: gold `text-[hsl(var(--high-moat))]`
  on the verb label. Per brief §11 Q3, no gold fill — only the small uppercase
  verb tag picks up the gold ink.
- **Risk of regression:** Tiny — new optional KPI defaulted to 0 in the API,
  consumer treats undefined as 0 via `?? 0` guard.

### 3. Sweet-spot row treatment everywhere (brief §7.8)
- **Files I will touch:**
  - `apps/web/app/(app)/dashboard/page.tsx` — Your-top list rendering.
  - `apps/web/app/(app)/opportunities/page.tsx` — list row rendering.
  - `apps/web/lib/api.ts` — extend `TopOpportunity` with `high_moat_score` +
    `is_sweet_spot`.
  - `apps/api/src/mactech_api/routes/me.py` — `TopOpportunity` Pydantic model
    grows the same two fields; SELECT widens.
- **Approach:** Row treatment is a 3px gold left border + an HpewBadge in the
  chip row. Both pages get the same conditional. To honor "never as fill"
  (Q3), I use `border-l-[3px] border-l-[hsl(var(--high-moat))]` — no `bg-`
  token use.
- **Risk of regression:** Minimal. Both list templates already exist with the
  same `border border-border bg-card` shell; we just override `border-l`.

### 4. Auto-brief on score ≥ 60 + promote `scope_one_sentence` to primary title (brief §7.2)
- **Files I will touch:**
  - `apps/workers/src/mactech_workers/tasks/score.py` — after a successful
    score upsert with `result.score >= 60` AND no existing `OpportunityBrief`
    row, fan out an `extract_structured_brief` call and persist the row.
    Add a `_maybe_generate_brief()` helper modeled on
    `_maybe_fetch_interested_vendors()`. Gate on `ANTHROPIC_API_KEY` and on
    presence of `opp.description_text`. Use the same Haiku-tier client
    pattern (the brief module already takes an `AnthropicLLMClient`).
  - `apps/api/src/mactech_api/routes/opportunities.py` — extend `OpportunityListItem`
    Pydantic model with `scope_one_sentence: str | None`; widen the SELECT to
    LEFT JOIN `opportunity_briefs ob` and project `ob.scope_one_sentence`.
  - `apps/api/src/mactech_api/routes/me.py` — same widening for
    `TopOpportunity` so the dashboard's top-5 inherits the same scope sentence.
  - `apps/web/lib/api.ts` — add `scope_one_sentence: string | null` on both
    `OpportunityListItem` and `TopOpportunity`.
  - `apps/web/app/(app)/opportunities/page.tsx` and `dashboard/page.tsx` —
    when `opp.scope_one_sentence` is present, render it as the `<h3>` title
    (15px/snug, two-line clamp) and demote the raw SAM `opp.title` to a muted
    second line. Preserve the raw title in `title=` for hover provenance.
- **Approach:** Worker side mirrors the existing
  `_maybe_fetch_interested_vendors` pattern: short-circuit if Anthropic key
  missing, run inside the same scoring transaction, swallow exceptions so a
  single brief failure can't tank the batch. Description-truncation budget
  already baked into `extract_structured_brief` (`MAX_DESCRIPTION_CHARS = 12000`).
- **Risk of regression:** Worker now does one extra Anthropic call per
  high-fit opp at the cost projected in §11 Q2 (~$0.20/day). The per-batch
  ceiling is bounded by `DEFAULT_BATCH_SIZE=25`. 25 × ~6s ≈ 2.5 min upper
  bound for Haiku briefs, well within the 18-min beat expiry.

### 5. Migrate `CyberPostureCard` to token system (brief §7.7)
- **Files I will touch:**
  - `apps/web/components/cyber-posture-card.tsx`.
- **Approach:** Replace
  - `bg-emerald-50 border-emerald-200 text-emerald-900/800` → `bg-success/10
    border-success/20 text-success`
  - `bg-red-50 border-red-200 text-red-900/800` → `bg-destructive/10
    border-destructive/20 text-destructive`
  - `bg-amber-50 border-amber-200 text-amber-900/800` → `bg-warning/10
    border-warning/20 text-warning`
  - `text-neutral-500/600` → `text-muted-foreground`
  - `text-brand-700` → `text-primary`
  Brief notes a "rename to `<CyberFitCard>`" and "what's missing" sub-rail
  in §7.7 — I'm deferring those (see "Deferred" below) and keeping the file
  name + API intact to limit blast radius. Just the tone migration.
- **Risk of regression:** Pure className substitution; tokens already have
  HSL values defined.

## Items I am deferring this pass

- **§7.3 — Restructure opportunity-detail page around bid/no-bid.** Large
  layout change, multiple panels, and the brief flags this as M-to-L effort.
  This is the right thing to do but doing it in the same pass as the
  high-moat strip + brief promotion makes the diff hard to review and
  bisect if anything regresses. Pick it up next iteration; the high-moat
  strip lands on the detail page next pass.
- **§7.4 — Left-rail "perspectives" replacing the filter sidebar.** Big
  IA shift; brief §11 Q4 confirms saved searches stay founder-private,
  so the rail design has to address per-founder views. Worth its own
  pass with screenshots to ground the conversation.
- **§7.6 — Brief tab affordance + must-haves grid.** The brief tab fix is
  small and tempting but it's coupled to §7.3 (the detail-page restructure).
  Defer.
- **§7.9 — Drop the "Open detail →" affordance.** Small polish; defer.
- **§7.10 — KPI strip from 4 → 3 tiles.** Demoting "Active pursuits" is
  reasonable but it changes the dashboard's vertical rhythm. Defer until
  the §7.1 strip lands so we can re-photograph the page.
- **§7.7 rename + "What's missing" sub-rail.** Doing the token migration
  only this pass; the rename to `<CyberFitCard>` and the new actionable
  sub-rail need an SPRS-vs-clauses delta that doesn't exist on the
  current endpoint payload. Defer pending an API addition.

Brief §11 Q5 explicitly says: defer the Feedback / thumbs-up affordance.
Honored — no thumbs widget anywhere in this pass.

## Open disagreements with the brief

None. The brief's §11 answers fully resolve the open questions. Aesthetic
direction (warm-paper + brand-teal + editorial-serif, gold for sweet spot,
no glass, no dark mode, no decorative icons) is well-judged and consistent
with the codebase's recent direction.
