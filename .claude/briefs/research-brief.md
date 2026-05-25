# UX Research Brief
Generated: 2026-05-25T09:29:00-07:00
Scope: Opportunity discovery + opportunity rendering. Specifically: `app/(app)/dashboard/page.tsx`, `app/(app)/opportunities/page.tsx`, `app/(app)/opportunities/[id]/page.tsx`, `components/todays-moves.tsx`, `components/cyber-posture-card.tsx`, `components/sidebar-nav.tsx`, `components/ui.tsx`, `lib/api.ts`. Out of scope: pipeline kanban, drafts, library, onboarding, settings (only mentioned where they touch discovery).

## 1. Product summary
MacTech CaptureOS is an internal BD weapon for a 4-person SDVOSB defense contractor: it ingests every federal SAM.gov opportunity, scores each one 0–100 against MacTech's NAICS / set-aside / capability profile, routes high-fit opps to the right founder by pillar (Security/Infra/Quality/Governance), and supports the workflow from triage to Sources Sought draft to capture package. The product just shipped a parallel "high-moat" scoring track tuned to MacTech's strongest win profile (OT/ICS cyber work mandated via UFGS 25 05 11 / 25 08 11) — but that track has zero presence in the web UI yet. The core daily question users open the app to answer is "given my profile, what should I bid on today?"

## 2. Stack & design system inventory
- **Framework:** Next.js 16.2 (App Router, RSC-heavy, `force-dynamic` on all data pages) + React 18.3 + TypeScript 5.6
- **UI library:** Hand-rolled shadcn-shape primitives in `components/ui.tsx` (Card, Section, PageHeader, Kpi, Badge, ScoreBadge, Button, LinkButton, EmptyState, Pillar, BackLink, Term, ExplainLink, NaicsBadge, NoticeTypeBadge, SetAsideBadge) — NOT the `npx shadcn` generator output. Radix Slot is the only Radix dep. `class-variance-authority` + `clsx` + `tailwind-merge` are wired.
- **Styling:** Tailwind 3.4 + a "gold copy" HSL CSS-variable token contract in `app/globals.css`. Light-first only (no `.dark` block, on purpose). Warm-paper background (`hsl(45 35% 97%)`), brand-teal primary (`hsl(178 58% 30%)` = #207b78), semantic `--success` / `--warning` / `--destructive`, four `--pillar-*` tokens. Body type is 15px sans (system stack) with `font-variant-numeric: tabular-nums` as default; an editorial serif (Iowan Old Style → Palatino → Georgia) is reserved for `display` headers on decision-oriented surfaces.
- **Existing primitives:** see ui.tsx above. Detail-page features: `AnnotatedProse` for inline jargon, `ExplainLink` / `ExplainRail` (an in-place right-rail "Explain this" surface that opens via `?explain=…` search param without losing state), `TermPopover`, `CmdK` (Cmd-K global search across opps/drafts/partners/past performance), `KeyboardList` (Linear-style j/k/Enter row navigation), keyboard shortcuts (g+letter go-to nav, ? for help modal), streaming `AskStreamingPanel`, `StreamingDraftButton`.
- **Existing design tokens:** Eight pages of HSL variables already establish a coherent cross-app contract (vetted / clearD parity). Pillar tokens are first-class. The biggest gap is no `--high-moat` / sweet-spot token yet — the new scoring track has no visual identity.

## 3. Activity signals (last 60 days)
- **Hot files (most edited in 60d):** `docs/PROGRESS.md` (28), `apps/web/lib/api.ts` (25), `apps/api/.../main.py` (24), `apps/web/app/(app)/dashboard/page.tsx` (20), `apps/web/app/(app)/opportunities/[id]/page.tsx` (19), `apps/workers/.../celery_app.py` (19), `packages/db/.../models/__init__.py` (18). The opportunity-detail page and the dashboard are by a wide margin the hottest UI surfaces — exactly where the ask is focused. Good news: redesign effort here lands on the most-touched code, so it won't bit-rot.
- **Active surface areas:** the four most recent commits (in chronological order) are `b09bb66 feat(intelligence): high-moat UFGS 25 / FRCS cyber scoring track`, `007d45f feat(web): worldclass internal-pages lift for layman DIB contractor`, `ee5bf2e feat(web): port vetted/clearD gold-copy token contract`, `e44699c ui(dashboard): tighten greeting`. Translation: the backend just shipped a major new ranking signal and the frontend just shipped a token contract — the next obvious move is to surface the new signal *through* the token contract. That's the brief.
- **Team size signal:** 140 commits from Patrick, 4 from another committer = effectively single-engineer. The product can absorb a focused, opinionated redesign; it cannot absorb 20 simultaneous leverage points. Pick the 5 that move the daily question.

## 4. User-reported pain points
GitHub MCP is not connected in this session, so I have no PRs/issues/reactions to cite as user evidence. There is also no first-party `Feedback` table in the schema (only `audit_events`), so there is no in-app feedback to surface either.

Recommendation for the human: this is a 4-person team that talks daily; the highest-value pre-design step is a 10-minute conversation that captures the actual phrases each founder uses when they say "this is annoying" on the opportunity feed. If you do nothing else before architecture, ask each founder to talk you through the last 3 opps they opened and which signal they actually used to decide bid/no-bid. That qualitative pass beats any code inference.

Inferred pain points from code structure (marked low/medium evidence strength):
- **High-moat signal is invisible** (HIGH evidence — direct code check). API returns `high_moat_score`, `is_sweet_spot`, `clause_hits`, `clearance_hits`, `role_hits`, `top_clearance`, `why_it_matters_seed`. Frontend has **zero** references to any of these. `grep -rn "high_moat" apps/web/` returns nothing. The list page sort still defaults to `score_desc` with no `high_moat_desc` option exposed in `SORT_LABELS`. This is the highest-leverage gap in the entire product right now: the team just built MacTech's "this is exactly the work we should win" detector and the UI literally cannot see it.
- **Cyber/OT clause evidence isn't shown where it would matter** (HIGH evidence). `CyberPostureCard` (in detail view) renders `clauses_identified`, `cmmc_level_required`, CUI/FCI/ITAR — but it pulls from `/opportunities/{id}/cyber-summary` (a different endpoint than the high-moat scoring path) and doesn't show *which UFGS clauses* fired the high-moat detector or which clearance roles (ISSM/ISSE/3PAO) triggered the role bonus. So the card that *looks* like "cyber posture" is actually about the tenant's posture vs. the solicitation's ask, not about why this opp is a high-moat fit for MacTech.
- **The list page has too many filters and not enough verbs** (MED evidence — visual density of `app/(app)/opportunities/page.tsx`). Score buckets, search, set-aside, notice type, assigned founder, NAICS, sort, page — eight controls on a row. A capture lead's actual question is two-dimensional ("for me, today, what should I open?"). The recently-shipped `/dashboard` "Today's moves" + KPI tiles already concedes this — they linkify to filtered list states. The list page should be a defaulted-correctly leaderboard, not a search UI.
- **The "why this matters" line is buried** (MED evidence). On the list, `why_it_matters` is line-clamp-2 in muted gray after title + agency. On the detail page it's in the bottom score panel behind a `<details>` for the breakdown. For a layman BD lead the "why" is the most important sentence on the page; right now it's two scrolls down.
- **Opportunity titles render as raw SAM.gov text** (LOW evidence, observed). SAM titles are notoriously ugly ("J--MAINTENANCE OF FACILITY DEDICATED CIRCUITS BLDG 4471 ROBINS AFB"). The brief generator (`brief.scope_one_sentence`) produces a clean "what this is" sentence but only inside the detail-page brief panel. The list shows the raw title.
- **The brief — the best surface for "sleek and beautifully parsed" — is opt-in** (MED evidence). On `opportunities/[id]`, `BriefAndDescriptionPanel` renders the plain-English brief if it exists, otherwise an empty state asking the user to click "Generate brief." There's no async pre-warm trigger that runs the brief generator for any opp scored ≥60 the moment it crosses the threshold. Result: the cleanest possible "opportunity in 30 seconds" view is the *last* thing a triaging founder sees.
- **No saved-search runner UI** (HIGH evidence). `SavedSearchOut` exists in `lib/api.ts`. The morning digest commit (`3c40db9 feat(digest): wire saved-search alerts through morning digest`) wires them through email. But there is no `/opportunities?saved_search=…` query path, no left-rail "Patrick's UFGS 25 / FRCS Cyber" entry, no first-class "open this saved view" affordance in the sidebar. The new high-moat-aware saved search the backend ships with has no front door.

## 5. Inferred user & critical path
- **Primary user persona (inferred + confirmed in CLAUDE.md):** four MacTech founders. Patrick (Security) and James (Infra) are code-fluent and likely live in CaptureOS daily; Brian (Quality) and John (Governance/Legal) are less code-oriented and check it episodically. Patrick is the engineer building it. The product is also a sales artifact (Phase 4+) so the UI must look credible to external DIB CISOs / BD leads / KOs visiting on demo — but optimize for the 4 daily users first.
- **Top 3 jobs-to-be-done on the discovery surface:**
  1. "Show me the 1–3 opportunities I personally should look at first today" (HPEW / sweet-spot triage).
  2. "Show me everything in my lane I haven't yet decided on" (untracked, scored ≥60, assigned to me).
  3. "Let me drill into one opp, decide bid/no-bid in 30 seconds, and either add to pipeline or move on" (decision triage).
- **Critical path for the primary job (today, observed in code):**
  1. Sign in via Clerk → `/dashboard`.
  2. Scan `TodaysMoves` (up to 3 ranked verbs: Decide / Review / Triage / RSVP / Position) — today this does NOT include "Pursue this sweet-spot opp."
  3. Click "Your top N" row → `/opportunities/{id}`.
  4. Scan: header chips → meta strip → pursuit panel → drafter panel → ask panel → two-column main (brief left / cyber posture + incumbent + capability matches right) → score breakdown (collapsed by default).
  5. Click "Add to pipeline" or bounce back.
- **Friction points observed in code:**
  - Triage requires scrolling past four pre-decision panels (PursuitPanel, DrafterPanel, AskPanel, then the brief) — they're useful *after* you've decided to pursue, but they sit above the "should we pursue?" evidence. The page layout is optimized for the second-visit, not the first-visit.
  - `BriefAndDescriptionPanel` uses URL hash anchors (`#brief-{id}` / `#raw-{id}`) as a fake tab pattern. That works, but `:target` styling isn't applied, so the "active" tab visual state is identical to the inactive one — the user can't tell at a glance which view they're seeing.
  - `cyber-posture-card.tsx` is one of two files still using raw hex tones (`bg-emerald-50`, `text-red-900`, `border-amber-200`) inside the post-token-contract codebase — it'll feel visually off-key on the page next to token-driven neighbors.
  - The "How CaptureOS works" 3-step block sits above the fold for every user who hasn't dismissed it. It's a one-time orientation. After dismissal it's recoverable from the footer, which is correct — but it shouldn't be eating prime real estate on day 2.
  - On opportunity-list `<details>` for "More filters" hides the sort control. Sort is a primary navigation verb on a ranked feed, not a power-user filter.

## 6. Recommended aesthetic direction
- **Direction: Editorial / B2G credibility, refined.** Keep the warm-paper + brand-teal + editorial-serif headers system that just shipped (commit `ee5bf2e`). This is the right call for the audience — KOs, CISOs, BD leads, and federal program staff respond to gravitas, not glow. The current token contract is well-judged; do not pivot it.
- **Rationale:** (1) The audience reads ugly PDFs all day; a calm, paper-feeling surface is a competitive advantage on focus. (2) The "veteran-owned, sober, plainspoken" voice in CLAUDE.md is already baked into the type system — Iowan Old Style serif on display titles signals "Booz Allen / Stripe" not "Palantir." (3) Dark cyber-command-center palettes would actively damage credibility with a CO who associates them with marketing decks, not real assessments. (4) The product is also MacTech's external-credibility surface; restraint reads as competence.
- **Visual language specifics:**
  - **Color foundation:** keep paper-50 / paper-100 / paper-200 with brand-teal (#207b78) as the single accent. Reserve `--warning` (amber) for deadlines and gaps, `--destructive` (red) for debarments and hard blockers, `--success` (green) for clean exclusions and submitted drafts. **Add one new restrained signal** for the new high-moat track: a single saturated hue, used sparingly — proposal: a `--high-moat` token at roughly `45 90% 45%` (a confident gold), used only on the High-Probability-Easy-Win badge, the high-moat segmented-control option, and a single underline accent on the score-breakdown component when the high-moat track is the dominant scorer. Gold is right because it reads as "this is the prize" without screaming and doesn't collide with the existing palette.
  - **Typography character:** body stays at 15px sans, tabular-nums on. Detail-page H1 stays italic-serif `display`. List-page row titles should bump from `text-base` to `text-[15px]/snug` with two-line clamp + an inferred plain-English title sourced from the brief's `scope_one_sentence` when available — fall back to SAM raw title. This single change is the biggest "sleek and beautifully parsed" win in the brief.
  - **Density:** the list view should be denser and more scannable, not less. Currently each row is `p-5` with a min-height around 130px; target ~92px row height with a fixed left-edge "rail" showing the score (or, for a sweet-spot opp, a small gold left border + HPEW chip).
  - **Motion posture:** static at rest. No card-lift hovers on rows (currently `hover:shadow-sm` — kill it for the leaderboard). One animated affordance only: the Ask Claude / Brief generation streams, which already work.
- **What to AVOID:** glass panels, dark mode, cyan accents, neon score colors, animated KPIs, illustration art, emoji of any kind (rule in CLAUDE.md), "cyber-grid" backgrounds, gradient buttons, anything that looks like a SaaS marketing site landing page.

## 7. Top UX leverage points (ranked)
Ranked by impact/effort. The top three are non-negotiable if you do nothing else.

1. **Wire the high-moat track end-to-end into the discovery UI.**
   - Problem: The backend's new sweet-spot detector (`high_moat_score`, `is_sweet_spot`, `clause_hits`, `clearance_hits`, `role_hits`, `top_clearance`, `why_it_matters_seed`) cannot be seen, sorted by, or filtered to from the frontend. The single most valuable signal the platform produces is invisible to the people who built it.
   - Evidence: `grep -rn "high_moat" apps/web/` returns zero hits. Commit `b09bb66` shipped the backend ten days ago and there is no companion frontend commit. The API exposes `?sort=high_moat_desc`, `?sweet_spot_only=true`, `?high_moat_min=80` per the brief context — none are reachable from a click.
   - Proposed direction: (a) Extend `OpportunityListItem` and `TopOpportunity` types in `lib/api.ts` to include `high_moat_score` + `is_sweet_spot`. (b) Add a third toggle to the segmented score-bucket control on `/opportunities`: "Sweet spots" (sweet_spot_only=true, sorts by high_moat_desc). (c) Add a sweet-spot row treatment: gold left-border rail + an "HPEW · UFGS 25" chip beside the ScoreBadge, only when `is_sweet_spot` is true. (d) On the dashboard, add a new top-of-page strip *above* "Today's moves" called "Today's sweet spots" that renders 0–3 HPEW opps inline as compact cards with the new gold accent. If zero sweet spots, render nothing (no empty state — gravitas requires not crying wolf).
   - Impact: High. Effort: M.

2. **Surface the plain-English brief on every list row and pre-warm it on score ≥60.**
   - Problem: SAM titles are formatted for the agency's internal system, not for human triage. The brief generator produces a one-sentence `scope_one_sentence` that is exactly the human-readable title the list wants. Today it lives only on the detail page and only after the user clicks "Generate brief."
   - Evidence: `OpportunityListItem` has no brief field; `BriefOut.scope_one_sentence` is fetched only on `/opportunities/{id}/brief`. The detail-page empty state in `BriefEmpty()` requires a click to generate. Brief generation already runs through Claude and is cached.
   - Proposed direction: (a) On score ≥60 (or any sweet-spot flag), enqueue brief generation in the same worker chain that already does scoring — the Celery work is small and the result is cached. (b) Include `scope_one_sentence` on the `/opportunities` and `/me/dashboard` list payloads. (c) Render it as the primary list-row title; demote the raw SAM title to a muted second line. (d) Keep the raw SAM title accessible via hover/title attribute for the BD lead who wants to verify provenance.
   - Impact: High. Effort: M.

3. **Restructure the opportunity detail page around the bid/no-bid decision, not the post-decision workflow.**
   - Problem: The top of the detail page today is: header → meta strip → PursuitPanel ("Add to pipeline") → DrafterPanel → AskPanel → main columns → score → score breakdown. Four of those panels are about *what to do after you've decided to pursue.* The user has not yet decided. They scroll past the decision evidence to get to the "do work" buttons.
   - Evidence: `app/(app)/opportunities/[id]/page.tsx` lines 232–246 place PursuitPanel + DrafterPanel + AskPanel before the brief panel. Layout order does not match decision order.
   - Proposed direction: New section order: (1) Header with score + HPEW chip if sweet-spot. (2) Meta strip (posted/deadline/set-aside/notice ID). (3) The brief panel (left column, full width if no explain rail) — this is the decision evidence. (4) A new compact "Why this is high-moat" strip when `high_moat_score >= 70`: shows `clause_hits` as badges with click-to-Explain, `top_clearance`, `role_hits`, and the `why_it_matters_seed` sentence — borrows the `CyberPostureCard` chrome. (5) Capability matches + incumbent intel (right column). (6) PursuitPanel + DrafterPanel + AskPanel (collapsed into a single "Take action" rail). (7) Full score breakdown (general + high-moat both visible, side-by-side). The new high-moat strip is the most important addition.
   - Impact: High. Effort: M-to-L.

4. **Replace the list page's filter sidebar with a left-rail of named, savable views ("perspectives").**
   - Problem: Eight filter controls + a search box force a capture lead to *configure* the feed every visit. The team already has `SavedSearchOut` typed and the morning-digest worker uses saved searches. None of that is exposed in the navigation surface.
   - Evidence: `SavedSearchOut` in `lib/api.ts` line 345; `SettingsResponse.saved_searches`; commit `3c40db9` ("wire saved-search alerts through morning digest"). The list page (`app/(app)/opportunities/page.tsx` lines 168–237) has no saved-search read path.
   - Proposed direction: Left-rail on `/opportunities` becomes a list of perspectives: "Sweet spots today," "My lane — untracked ≥60," "Sources Sought in my NAICS this week," "Deadlines ≤7d," "All opps." Each is a saved search with stable URL (`/opportunities?view=sweet-spots`). The current filter controls become a "Refine this view" drawer that collapses by default. Add a "Save as perspective" button after manual refinement. This is the Linear / Notion "views" pattern and it's right for this audience.
   - Impact: High. Effort: M.

5. **Add a sweet-spot deadline alert to "Today's moves."**
   - Problem: `TodaysMoves` ranks deadlines, drafts, high-fit untracked, events, recompetes — but not "an HPEW opportunity just landed in your lane today." A founder who only looks at the dashboard misses the most valuable signal.
   - Evidence: `components/todays-moves.tsx` lines 55–168 do not reference high-moat or sweet-spot. `DashboardKpis` has no `your_sweet_spots_open` field.
   - Proposed direction: Add a `your_sweet_spots_open` KPI to `/me/dashboard`. Insert a new ranked Move at slot #1 ("Pursue: N sweet-spot opp[s] dropped in your lane this week") when count > 0, using the new gold tone, linking to `/opportunities?view=sweet-spots`. Demote "high-fit untracked" to slot #3 since "high-fit" is the more general superset.
   - Impact: High. Effort: S.

6. **Fix the `BriefAndDescriptionPanel` tab affordance and elevate the brief.**
   - Problem: The brief/raw toggle uses anchor links without a `:target` style, so the "active" tab is visually indistinguishable from the inactive one. The brief should also be the default *and* render its `must_haves`, `red_flags`, `suggested_teaming` more scannably than the current bulleted list.
   - Evidence: `app/(app)/opportunities/[id]/page.tsx` lines 922–940 (the two anchors have the same styling logic regardless of `:target`).
   - Proposed direction: Replace anchor-tab with a state-aware tab strip (server-component–friendly: use a search param `?view=brief|raw` and conditional className). Promote `must_have_requirements` to a 2-column grid with checkbox-like dot affordance. Keep `red_flags_for_small_biz` amber-bordered. Add an inline "Copy brief to clipboard" button — BD leads often paste these into Slack/Teams. Add an "Send to teaming partner" mailto stub once partner email is in the library.
   - Impact: Med. Effort: S.

7. **Migrate the `CyberPostureCard` to the token system and rename it to clarify intent.**
   - Problem: One of two remaining hex-tone holdouts in the post-token-contract codebase. Also: the card name suggests "MacTech's cyber posture" but actually means "MacTech's posture vs. this solicitation's cyber ask." On a list with the new high-moat strip nearby, this becomes confusing.
   - Evidence: `components/cyber-posture-card.tsx` uses `bg-emerald-50`, `text-red-900`, `border-amber-200`, `text-neutral-500`, etc. throughout. Compare to the token-driven neighbors that use `text-muted-foreground` / `bg-success/10` etc.
   - Proposed direction: Rename to `<CyberFitCard>` ("Cyber fit · your posture vs. their ask"). Convert tones to semantic tokens. Add an explicit "What's missing" sub-rail that lists clauses cited in the solicitation that the tenant's SPRS profile doesn't yet cover — turns the card from informational to actionable.
   - Impact: Med. Effort: S.

8. **Add an explicit `is_sweet_spot` row treatment to the list AND the dashboard's "Your top N."**
   - Problem: Without a visual distinction, a sweet-spot opportunity and a generally-high-scoring opportunity look identical on every surface. The whole point of the new track is that one of these things is *not* like the other.
   - Evidence: `app/(app)/opportunities/page.tsx` row template (lines 310–384) has no conditional treatment. `app/(app)/dashboard/page.tsx` `your_top` template (lines 406–460) ditto.
   - Proposed direction: Sweet-spot rows get (a) a 3px gold left border, (b) a small "HPEW" pill beside the ScoreBadge, (c) the `why_it_matters_seed` sentence rendered above the regular `why_it_matters` in a slightly bolder weight. Three-level visual hierarchy on the list: sweet-spot > top-scored > everything else. Do not animate this — gravitas.
   - Impact: Med. Effort: S.

9. **Move the "Open detail →" affordance and tighten list-row affordance footprint.**
   - Problem: The list-row currently has an explicit `Open detail →` link inside an already-clickable card. Hover state lifts the card with a shadow. Two competing affordances; both feel a bit Web-1.0.
   - Evidence: `app/(app)/dashboard/page.tsx` line 455-457; `app/(app)/opportunities/page.tsx` lines 314-315 use `hover:shadow-sm`.
   - Proposed direction: Whole row is the link (already true). Drop the explicit "Open detail" CTA text. Replace shadow-on-hover with a subtle background tint (`hover:bg-accent/40`) and a right-edge chevron that slides 2px on hover. Calmer, denser, more "leaderboard."
   - Impact: Low-Med. Effort: S.

10. **Tighten the KPI strip → make it three tiles, not four.**
    - Problem: Four KPIs is one too many on a strip designed to be scanned in two seconds. "Active pursuits" is the weakest of the four — it's a pipeline-health metric, not a discovery question, and `/pipeline` is one click away in the sidebar.
    - Evidence: `app/(app)/dashboard/page.tsx` lines 271–321.
    - Proposed direction: Three tiles, all framed as discovery questions: "Sweet spots today" (new, gold), "High-fit untracked," "Deadlines ≤7d." Move "Active pursuits" + "Drafts to review" into a smaller "Your work" strip below "Today's moves" — they're work-in-flight metrics, not "what should I bid on today" metrics.
    - Impact: Low-Med. Effort: S.

## 8. Out of scope / explicit non-goals
- **Do not touch the pipeline kanban (`/pipeline`)** on this pass. It's the post-decision surface; conflating it with discovery doubles the redesign surface area without serving the brief.
- **Do not redesign the drafts surface, library, settings, or onboarding.** Each is independently working and any change there will cost focus the redesign can't spare.
- **Do not introduce a dark mode.** Audience signals strongly point to light-first; the token contract was deliberately built without a `.dark` block in commit `ee5bf2e`. Honor that decision.
- **Do not replace the hand-rolled UI primitives with the shadcn CLI generator.** The current primitives are tuned to the token contract; ripping them out is a multi-week regression risk for cosmetic parity gain.
- **Do not redesign the Ask-Claude streaming panel.** It works and the streaming UX is good.
- **Do not redesign auth/Clerk surfaces** — handled by upstream Identity Command Center, recent commits show stability work landed.
- **Do not add a "compare opportunities" feature** even if it sounds clever. The team is 4 people; they decide in conversation, not in a comparison view.
- **Do not add new external dependencies** without a written tradeoff in CLAUDE.md per the operating agreement.

## 9. Success criteria for the verifier
- A founder visiting `/dashboard` on a day when at least one sweet-spot opp exists in their lane sees an HPEW marker above the fold (no scroll on a 1440×900 viewport).
- The `/opportunities` list page exposes a "Sweet spots" toggle that issues `sort=high_moat_desc&sweet_spot_only=true` to the API. Tested by clicking the toggle and inspecting the network request.
- Every opportunity list row renders a human-readable title — either `brief.scope_one_sentence` when available, or the raw SAM title with no fallback string like "—" or "untitled."
- Sweet-spot rows have a visually distinct, non-animated treatment from regular high-score rows. The treatment uses the new `--high-moat` token, not a hardcoded color.
- The opportunity detail page renders the brief (`Plain-English brief` tab) as the default visible content; the raw SAM text is reachable in one click. The active tab is visually distinct from the inactive tab — verifiable by screenshot diff.
- A new "Why this is high-moat" strip appears on the detail page when `high_moat_score ≥ 70`, showing `clause_hits` (UFGS / DFARS / FAR badges), `top_clearance`, `role_hits`, and `why_it_matters_seed`. The strip does NOT appear when score is below threshold.
- The `CyberPostureCard` (or its renamed successor) uses zero hardcoded hex/tone classes — only semantic tokens. Verifiable via `grep -E "bg-(red|amber|emerald|neutral)-[0-9]" components/cyber-posture-card.tsx` returning nothing.
- Contrast ratio ≥ 4.5:1 for body text on `--background` and on `--card`; ≥ 3:1 for the new `--high-moat` token at common foreground/background pairings. Use `npx @axe-core/playwright` (already a devDep) for the sweep.
- Mobile layout at 375px width: the opportunity list does not horizontally scroll; the detail-page two-column layout stacks into a single column at <lg. Existing responsive utilities already imply this; verify it.
- Keyboard navigation: j/k moves through list rows, Enter opens, Cmd-K opens search, ? shows shortcuts — all already working; verify the new sweet-spot toggle is reachable via Tab and announces correctly to a screen reader (`aria-pressed` on the segmented control).
- No emoji introduced anywhere in product UI (CLAUDE.md rule). Currently there is one stray check glyph in `cyber-posture-card.tsx` — that's existing tech-debt, fine to leave or replace with an icon, but do not add more.
- No new `console.log`, no new `TODO` comments without a date, no new `any` types in TypeScript additions.

## 10. Open questions for the human
1. The high-moat track is currently Patrick-tuned (UFGS 25 / FRCS cyber). Should the sweet-spot surface render the same for Brian, James, John — or do they get their own pillar-shaped "high-moat" tracks later? This determines whether the gold accent is universal or Security-pillar-only.
2. The brief's `scope_one_sentence` is generated by Claude. If we promote it to be the primary list title for every score-≥60 opp, we'll generate ~1 brief per scored opp. Cost is probably trivial (Haiku, single-sentence prompt) but worth confirming the budget before wiring the worker chain.
3. Is the gold `--high-moat` token (`45 90% 45%`) on-brand for MacTech? The four pillar tokens already cover the spectrum; gold is a fifth signal. If you'd rather extend the existing palette (e.g., a deeper teal variant or a brighter brand-700), say so and I'll specify accordingly in the architect pass.
4. Saved searches: should the left-rail "perspectives" be founder-private or tenant-shared by default? `SavedSearchOut.owner_founder_slug` suggests private; the morning digest infra suggests they're also being used as shared filters. This affects the "Save as perspective" affordance.
5. Is there appetite for a `Feedback` model + a one-key thumbs-up/thumbs-down "was this opp scored right?" affordance on the detail page? Right now there's no closed-loop signal from triage back to scoring. This is a Phase 2 idea, not a Phase 1 brief item, but flagging now since it's the kind of thing that's much cheaper to add at the same time as the score-breakdown redesign.

## 11. Human responses

**Q1 — High-moat scope: Universal across founders.** The gold accent + Sweet Spots strip render for all four pillars. Brian / James / John see the high_moat_score column header even when their pillar's track isn't tuned yet — the rows will show low or null high-moat scores until those tracks ship, which is acceptable. One consistent surface across the team beats per-pillar UI divergence.

**Q2 — Auto-brief budget: Yes, generate briefs for every score ≥ 60.** Estimated ~$0.20/day at MacTech scale. Architect should wire the Haiku scope-extraction call as a post-score worker step so the list shows the human-readable `scope_one_sentence` as the primary title and demotes the raw SAM.gov text to a muted secondary line.

**Q3 — Gold accent: Use the restrained gold token.** `45 90% 45%` federal-procurement gold. Strictly left-border + corner-marker on sweet-spot rows; never as fill or background. Reads as gravitas, not bling — matches the existing warm-paper + brand-teal + editorial-serif system.

**Q4 — Saved searches: Founder-private.** Matches the existing `SavedSearch.owner_founder_id` schema and the per-founder morning digest. Sharing can come later as an explicit affordance — not the default.

**Q5 — Feedback model: Defer to Phase 2.** Out of scope for this pass. The brief explicitly framed this as Phase 2 and the architect should NOT add a thumbs-up/down affordance during this iteration. Revisit after the first week of high-moat scoring data lands.
