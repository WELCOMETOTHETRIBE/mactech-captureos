# UX Research Brief — CaptureOS Authenticated Suite, Continuity & World-Class Lift

Generated: 2026-05-08T21:30:00-07:00
Scope: every page under `apps/web/app/(app)/**` (`/dashboard`, `/opportunities`, `/opportunities/[id]`, `/pipeline`, `/pursuits/[id]`, `/library`, `/drafts`, `/drafts/[id]`, `/forecasts`, `/recompetes`, `/events`, `/settings`), the `(app)/layout.tsx` shell, `components/sidebar-nav.tsx`, and shared primitives (`PageHeader`, `Section`, `Card`, `Kpi`, `EmptyState`, `Term`/`TermPopover`/`ExplainRail`, `Badge`/`ScoreBadge`/`Pillar`, `TodaysMoves`).

This pass picks up where the gold-copy port (commit `ee5bf2e`) left off. Token contract, auth shells, footer, and shadcn primitive scaffolding shipped successfully. The verifier's verdict was SHIP. This brief assumes that foundation and asks: now that every authenticated page renders on a token-driven warm-paper editorial frame, what's blocking it from being world-class for a layman DIB contractor?

---

## 1. Suite-continuity audit

"Suite continuity" in CaptureOS means: same shell shape (sidebar + topbar + main + footer), same `PageHeader` rhythm, same KPI/badge/score vocabulary, same jargon-helper system (`Term`/`TermPopover`/`ExplainRail`), same sober-veteran-owned voice across every authenticated page.

### Already consistent (post-ee5bf2e, verified)
- **Shell shape.** `apps/web/app/(app)/layout.tsx:18-103` is a single-source `flex min-h-screen / grid 240px_1fr / footer` for every page. Token-driven (`bg-background`, `border-border`, `bg-card`).
- **`PageHeader` adoption.** All 12 in-scope routes mount `<PageHeader>` from `components/ui.tsx` (verified by grep — 14 callsites including nested `/library/...`, `/settings/founders/...`). Exception: opportunity detail does NOT use `PageHeader`; it inlines its own header strip with serif italic title (see §2).
- **Jargon vocabulary.** `Pillar`, `NaicsBadge`, `SetAsideBadge`, `NoticeTypeBadge`, `ScoreBadge` are imported and used by every list/detail page that needs them. Pillar tokens (`--pillar-*`) flow through these consistently.
- **Token utilities** (`bg-card`, `border-border`, `text-muted-foreground`) used by `(app)/layout.tsx`. Footer is paper-100 token-driven.
- **Cmd-K + KeyboardShortcuts** mounted globally in the shell (one mount, listens app-wide).

### Drifting page-to-page (the real problem this pass should fix)

1. **Two parallel color systems running simultaneously.** The shell speaks in tokens (`bg-card`, `text-muted-foreground`); every page body speaks in legacy palette (`border-paper-200`, `bg-white`, `text-neutral-500`, `text-brand-700`). Grep counts: **497 legacy palette hits** across `app/(app)/`, **37 in the three hottest pages alone** (dashboard, pipeline, opportunity detail). The legacy aliases still resolve, so visually the result is fine — but the contract is split. Future cross-suite ports require the architect to migrate twice.
2. **`PageHeader` used inconsistently for the SAME page archetype.** Opportunity list uses default sans `PageHeader` (`opportunities/page.tsx:80`). Pursuit detail uses `display` italic-serif (`pursuits/[id]/page.tsx:215-243`). Opportunity detail ignores `PageHeader` entirely and rolls its own h1 inside a card (`opportunities/[id]/page.tsx:162-229`). Three patterns for three structurally identical "page top" surfaces.
3. **Primary-action affordance inconsistent.** "Add to pipeline" uses `bg-neutral-900` black button (`opportunities/[id]/page.tsx:521`). "Capture Package" uses `bg-brand-700` teal (`pursuits/[id]/page.tsx:231`). "Sign in" was just unified to teal in the auth pass. "Continue setup" on the dashboard uses `bg-amber-700` (`dashboard/page.tsx:154`). "Save" buttons in the pursuit page are a mix of black (`bg-neutral-900`) and teal (`bg-brand-700`). The user can't learn a single "this is the primary action" rule.
4. **Stage / pursuit color vocabulary forks.** Pipeline page hardcodes win/lost stage tones (`bg-emerald-600`, `bg-red-600` — `pipeline/page.tsx:376-380`). Opportunity detail's `PURSUIT_STAGE_TONE` map gives `propose: "amber"` and `submit: "violet"`. Pursuit detail's `STAGE_TONE` map gives `pursue: "amber"`, `propose: "violet"`, `submit: "brand"` (`pursuits/[id]/page.tsx:50-58`). Three different pursuit-stage palettes living in three files. The user sees the same lifecycle paint differently depending on which page they entered through.
5. **Back-affordance pattern forks.** Opportunity detail has `← All opportunities` (`opportunities/[id]/page.tsx:155`). Pursuit detail has `← Pipeline` (`pursuits/[id]/page.tsx:208-213`). Draft detail has `← All drafts` *and* `Source opportunity →` on the right (`drafts/[id]/page.tsx:60-74`). Library/settings sub-pages mostly use just `<PageHeader>` with no back link. There's no rule for when a back link appears, where it sits, or what it says.
6. **Voice in empty states is inconsistent.** Pipeline first-time empty state is a 4-step pedagogical wall (`pipeline/page.tsx:453-525`) — strong, consistent with brand. Library empty states teach the user (`library/page.tsx:107-124`) — also strong. But `events/page.tsx:37-58` empty state explains the worker schedule + sends user to `/forecasts` to "check the diagnostic" — that's an ops voice, not a layman voice. `forecasts/page.tsx:96` short-circuits to the `<IntegrationDiagnostic>` component when empty (instead of a true empty state) which assumes the user understands what an integration is. `recompetes/page.tsx:194` correctly teaches what a recompete is — strong. Inconsistent quality means new users learn that some empty states help and some don't.
7. **The `Term`/`TermPopover` system is one of CaptureOS's strongest brand assets but is used unevenly.** 52 callsites in `app/(app)/`. Strong coverage in opportunity detail, pursuit detail, solicitation-panel, cyber-posture-card, tenant-eligibility-card. **No coverage** in: `forecasts/page.tsx` (writes "RFP expected", "Set-aside:", "POP", "Federal footprint" bare), `recompetes/page.tsx` (writes "POP ends", "Federal footprint", "SEC EDGAR", "set-aside scope" bare), `events/page.tsx` (writes "Pre-solicitation", "Industry day", "OSBP" bare), `pipeline/page.tsx` (writes "Lead", "Qualify", "Pursue", "Propose", "Submit" as stage labels with no helper), `settings/page.tsx` (writes "UEI", "CAGE", "NAICS matrix", "tier: primary/secondary" bare), `drafts/page.tsx` (writes "Sources Sought", "RFP response", "compliance matrix" bare). Six pages where a layman reading would hit a wall.
8. **Sidebar active-state color forks from the rest of the page.** `sidebar-nav.tsx:82` uses `border-brand-700 bg-brand-50 text-brand-900` (legacy palette literal) — the only place in the app shell that talks legacy. Cosmetic identical, but it's a token-contract gap right inside the shell.

---

## 2. Per-page audit

### `/dashboard` (`apps/web/app/(app)/dashboard/page.tsx`, 814 lines)

**Strengths:** This is the most-iterated page (19 commits in 60d) and it shows. `TodaysMoves` (lines 326-336) is a genuine "what should I do right now?" surface — Linear-quality. KPI strip (270-320) is action-linked, not vanity. SPRS chip (200-267) is the only place in the product where the layman sees "what's my CMMC eligibility?" at a glance — and it has `<TermPopover kind="sprs">` wrappers (203-211). Score-tone language is in plain English ("Strong fit — pursue", "Worth a look", "Watch list", "Long shot" — `ui.tsx:212-219`).

**Drift / friction:**
- **No `Term`/`TermPopover` on the four KPI tiles.** "High-fit, untracked" KPI says `scored ≥60, not yet in your pipeline` (line 282). Layman: what's "high-fit"? what's a "score"? The hint should link the score concept to its plain-English explanation.
- **The `HowItWorks` block** (484-527) renders a 3-step explanation but uses `bg-brand-700` black-circle step numbers and a dismissable affordance — that's good, but the language uses `Lead → Qualify → Pursue → Propose → Submit → Won/Lost` (line 521) without any helper. The first time a small DIB contractor sees those words, they don't know if "Qualify" means "qualify the opp" or "qualify yourself."
- **`ComingUpRail` at lines 565-633** has three columns, each linking to a dedicated page. Good. But the column headers — "Coming to SAM", "Where to be", "Recompetes" — hide what the user gets. "Coming to SAM" and "RFP in 12d" assume the user knows what SAM is and what an RFP timeline looks like.
- **3-month-old `bg-paper-200`/`bg-paper-50`/`bg-white` literals** at lines 650, 651, 656, 661, 672, 689, 731, 791. These are the legacy-palette holdouts — visually identical to tokens, but they fork the contract. The shell speaks tokens; the dashboard body speaks paper-*.
- **`text-amber-700`/`text-rose-700` literal aging colors** in `ComingUpForecastRow` (lines 741-744) and `ComingUpEventRow` (799-802). The semantic system shipped in `ee5bf2e` has `--warning` and `--destructive`. These should be `text-warning` / `text-destructive`.
- **Mobile posture:** the dashboard is responsive at the structural level (KPI strip is `grid-cols-2 md:grid-cols-4`). But the SPRS chip (line 201) + onboarding banner (142) + first-feed banner (166) all use `flex flex-wrap items-center justify-between gap-3` — fine on desktop, on a 375px viewport the action button drops below the text without explicit ordering, putting the CTA below the fold of a critical onboarding nudge.
- **The `firstFeedLoading` banner** (165-195) uses `bg-brand-50 border-brand-200` (legacy palette). Same content as before; should be `bg-primary/10 border-primary/20`.

**"What should I do here?"** answer: very clear. `TodaysMoves` + KPI strip + Your top + Coming-up rail is a strong information hierarchy. Score: **8/10** — the top of the dashboard is genuinely world-class; the bottom (HowItWorks + ComingUpRail) drifts off the contract.

### `/opportunities` (list, `apps/web/app/(app)/opportunities/page.tsx`, 540 lines)

**Strengths:** Quick-filter score-bucket strip (98-164) with plain-English labels ("Top fit", "Worth a look", "Watch list", "All") is the right shape — segmented control of the most-used filter. Card layout (310-385) with score on the left, deadline on the right, why-it-matters as the third row, hover-revealed extra chips (335-344). Pagination is clean.

**Drift / friction:**
- **Legacy palette wall.** Every literal: `border-neutral-200`, `text-neutral-500`, `bg-white`, `text-brand-700`, `bg-brand-700` (lines 89, 98, 121, 124-126, 147, 197, 224, 273, 285, 294, 315, 350-381, 398, 463-466, 508-535). The page is essentially zero-tokenized.
- **Primary action color is black** (`bg-neutral-900` — line 124, 273, 294, 463). Inconsistent with the auth pages and primary-button shadcn variant which are brand teal. This page shipped before the gold-copy port; it's still on the old "black is primary" pattern.
- **No Term wrapping on the filter chips.** "Set-aside", "Notice type", "NAICS" filter sidebar (170-211) — bare. These are the exact terms a layman doesn't know. The hover-revealed `NaicsBadge` chip on cards has the explanation, but the filter sidebar — where a new user goes to narrow results — doesn't.
- **The empty state** (242-300) is good — distinguishes "no results match filters" from "ingestion still loading" with different bodies + actions. The verbiage "SAM.gov ingestion runs every 2h and scoring every 20m" is ops-tone, not layman.
- **Mobile posture:** filter sidebar is left column at `lg:col-span-1` and main is right `lg:col-span-3` — fine. At <`lg`, the filter sidebar stacks above the results. That's correct, but on a 375px viewport the user scrolls through the entire facet sidebar before seeing the first opportunity. There's no "show filters" collapse on mobile.

**"What should I do here?"** answer: clear if you've been onboarded. Less clear for a brand-new layman — they land on a list of jargon-tagged opportunities and the four score buckets are the only ergonomic. Score: **6/10**.

### `/opportunities/[id]` (`apps/web/app/(app)/opportunities/[id]/page.tsx`, 1206 lines)

**Strengths:** The flagship surface. Triage-first layout (the user can answer "should I bid?" above the fold): score badge + notice-type chip + set-aside chip + NAICS chip + deadline + the brief's must-haves and red-flags (1077-1097). `<ExplainLink>` and `<Term>` wrap every chip (171-198) — the strongest jargon coverage in the product. Plain-English brief tabs (962-1062) with structured Scope/must-haves/red-flags/teaming. PursuitPanel inline (488-599) means "add to pipeline" sits right at the decision point. AskPanel + DrafterPanel collocated at top (239-246). ExplainRail right-side (769-835) is a brand differentiator.

**Drift / friction:**
- **Header doesn't use `PageHeader`.** Lines 162-229 inline the eyebrow + serif italic title + chip row — duplicating the `display={true}` pattern from `PageHeader`. Should use `<PageHeader display eyebrow={agency} title={title} subtitle={...}>`. Currently a one-off.
- **The pursuit-stage tone map is inconsistent with the pipeline page.** Lines 468-476 vs `pipeline/page.tsx:50-58`. Single source of truth needed.
- **Inline buttons re-implement the shadcn-shaped button.** `DetailStageBtn` (642-678) and the literal `bg-neutral-900`/`bg-emerald-600`/`bg-red-600` buttons (520-525, 654-660). After the gold-copy port we have `components/ui/button.tsx` with `cva` + variants — but this page predates that scaffold and never adopted it. Each sub-component has its own button shape.
- **`AskPanel` recent-questions list** (894-905) doesn't show "this answer cites X capability statement / Y past performance" — that's the citation surface CaptureOS uniquely earns trust on, and it's invisible on this surface.
- **The score breakdown is a hover-only `<details>`** (375-430). The `<details>` summary is a small uppercase eyebrow ("Score breakdown") that a layman might miss. Worth promoting to a more visible "Why did we score this 78?" affordance — that's exactly the question a new user asks.
- **Mobile posture:** ExplainRail is the right column at `lg:grid-cols-[minmax(0,1fr)_22rem]`. Below `lg` it stacks below the main column — good. But the in-page panels (PursuitPanel, DrafterPanel, AskPanel, BriefAndDescription, IncumbentIntel, CapabilityMatches, ScoreBreakdown) are six full-width sections in a row. On a 375px viewport the user scrolls forever before reaching the score rationale.

**"What should I do here?"** answer: very clear for "should I bid this?" The score + brief + chips + add-to-pipeline button live above the fold. Score: **8.5/10** — only beaten by dashboard for polish; the inline-button divergence is the main thing keeping it from world-class.

### `/pipeline` (`apps/web/app/(app)/pipeline/page.tsx`, 548 lines)

**Strengths:** Real kanban with stage-aging color rings (red at 14d, amber at 7d, lines 239-253). Owner filter pills with counts. First-time empty state is a strong 3-step pedagogical block (453-525). Terminal stages (won/lost) collapsed to a smaller row.

**Drift / friction:**
- **Stage labels (`Lead`, `Qualify`, `Pursue`, `Propose`, `Submit`, `Won`, `Lost`) have no `Term` wrapper.** Layman: "what's the difference between Pursue and Propose?" Five stages with no inline help — for a user who's never run a federal capture pipeline this is a wall.
- **Aging colors hardcoded.** `border-red-300`/`border-amber-300`/`text-red-700`/`text-amber-700` (lines 240-248). Should be `border-destructive/40`/`border-warning/40` semantic.
- **Stage-action buttons are ad-hoc inline.** `StageBtn` (362-398) with primary as `bg-neutral-900`, won as `bg-emerald-600`, lost as `bg-red-600`. Should be variants on the shadcn `Button` primitive.
- **`bg-emerald-600` and `bg-red-600`** for won/lost terminal-buttons aren't tokenized — even though `--success` and `--destructive` exist.
- **No keyboard navigation** in the kanban. Cmd-K helps you find a pursuit but once you're on the kanban, no `j`/`k` row movement, no `→` advance like the opportunity list has via `KeyboardList`.
- **Card density.** Each card has score + notice-type + title + set-aside + NAICS + deadline + owner + aging + 6 action buttons + remove (lines 256-360). At 5-column kanban width on lg+, each card is ~200px wide and the action button row wraps to two lines. Visually cramped.
- **The terminal-stage card** has a `compact` mode (line 339-357) with a tiny "remove" link. Won/Lost cards should give the user one more thing — a "what worked?" / "what killed it?" prompt — currently they're a graveyard.

**"What should I do here?"** answer: clear once you know the stages. For a layman: muddled — they have to read 5 stage names and decide which column to drop a pursuit in.  Score: **6.5/10**.

### `/pursuits/[id]` (`apps/web/app/(app)/pursuits/[id]/page.tsx`, 703 lines)

**Strengths:** Genuine deep-work surface. `BidDecisionForm`, `NotesEditor`, `WinStrategyEditor`, `PastPerformanceSelector`, `KeyPersonnelSelector`, `TeamingPartnerSelector` (lines 247-285), `SolicitationPanel` (260-267), `AmendmentsPanel`, `AgencyIntelCard`, `WebMentionsCard`, `AuditTrailCard`. This is where a pursuit lives. Uses `<PageHeader display>` + back link + capture-package CTA.

**Drift / friction:**
- **Long scroll, no in-page navigation.** 11 sections stacked vertically. There's no left rail, no anchor list, no "jump to win strategy" — the user scrolls. On 1440 wide this is fine; on 1024 (typical SDVOSB user laptop) it's a workout.
- **Win-strategy editor and notes editor are side-by-side textareas** (249-256) at lg+, stacked at <lg. Good. But the `placeholder` (442-465) is the only guidance — there's no "what's a discriminator?" `Term` wrap on the label.
- **PursuitMetaStrip** (336-367) shows Stage / Owner / NAICS / Deadline. Stage label has no Term wrap. NAICS has Term wrap (354-358) — good. Why are some labels wrapped and others not? Inconsistent.
- **`Card` titles are passed strings, not `<Term>`** despite the title type being `ReactNode`. E.g. `Card title="Win strategy"` (426) — should `<Term kind="proposal" value="win_themes">Win strategy</Term>`.
- **Save buttons and stage-action buttons** use raw black `bg-neutral-900` and brand-teal `bg-brand-700` mixed (471-476, 547-553, 609-616, 657-664). Same primary-action ambiguity as everywhere else.
- **`Pillar` rendered on `KeyPersonnelSelector` (line 601)** — good, uses pillar tokens. But the same component renders nothing in `PastPerformanceSelector` even though past performance has a `related_founder_slugs` field. Asymmetric.
- **Danger zone** (299-320) is at the bottom of an 11-section page — by the time the user scrolls there, they've forgotten the name of the pursuit. Maybe collapsed by default.

**"What should I do here?"** answer: less clear than the opportunity detail. The opportunity detail has one CTA (Add to pipeline / Open in SAM); this page has 11 simultaneous CTAs (save notes, save win strategy, save selection × 3, advance stage, mark won/lost, generate capture package, regenerate compliance matrix, etc.) and nothing tells the user where to start. Score: **6/10**.

### `/library` (`apps/web/app/(app)/library/page.tsx`, 531 lines)

**Strengths:** Three-section structure (capability statements, past performance, teaming partners) with summary stats at top (51-79). Empty states are pedagogical (107, 222, 342). Section headers consistent (486-511). Cards per item with edit/delete affordances.

**Drift / friction:**
- **Bare jargon.** "Capability statements", "Past performance", "Teaming partners", "embedded for vector match", "NAICS coverage", "distinct codes referenced" (lines 53-78). All bare. Layman: "what does it mean for a capability statement to be 'embedded'?"
- **Unicode-glyph CTAs.** "⬆ Import PDF" (88, 113, 207) — typographic glyph, not emoji, but the visual treatment is icon-styled. Inconsistent with the gold-copy direction (no decorative icons on cards). Should be a token-driven button with a variant.
- **`bg-blue-50 text-blue-700` for "embedded" badge alternate** (138). Should resolve through the semantic-token map (probably `success`).
- **Buttons on this page are "+ Add cluster", "+ Add record", "+ Add partner"** with `bg-neutral-900` (97, 213, 333) — same primary-action ambiguity.
- **Set-aside certification badges on teaming partners use `tone="violet"`** (407) — the legacy violet maps to the future pillar/info token but isn't promoted yet.
- **Mobile posture:** capability statements are `md:grid-cols-2`; past performance and teaming partners are flat lists. Reasonable.

**"What should I do here?"** answer: clear if you know what these three terms mean. For a layman setting up the product for the first time, the eyebrow says "Capture library" and three sub-headers shout "capability statements / past performance / teaming partners" — they need a "what is this for?" sentence per section. The subtitles do this, but they're long enough that a hurried user skips them. Score: **6/10**.

### `/drafts` (list, `apps/web/app/(app)/drafts/page.tsx`, 99 lines)

**Strengths:** Compact. Each draft is a row with status / type / version / created date + opportunity title + model & token usage. The empty state's `Find Sources Sought opps` button is a smart redirect.

**Drift / friction:**
- **"Sources Sought", "RFP response", "compliance matrix"** are draft-type chips (lines 13-18, 65) with no Term wrap.
- **Status badges** (`draft / reviewed / submitted / archived`) — no Term wrap. A first-time user wouldn't know whether to mark "reviewed" then "submitted" or skip "reviewed."
- **Kbn shortcuts** — list is not keyboard-navigable. `KeyboardList` is wrapped on opportunity list and dashboard's "your top"; not here.
- **`text-blue-700` for filtering link** (175 in elsewhere; this page itself uses `text-brand-700` consistently) — fine.
- **Token literals.** Every classname is legacy palette.
- **Action buttons (`bg-neutral-900` for "Find Sources Sought")** — same primary-action ambiguity.

**"What should I do here?"** answer: clear if you've drafted before. For a layman: "what's the difference between 'reviewed' and 'submitted'?" is unanswered. Score: **6.5/10**.

### `/drafts/[id]` (`apps/web/app/(app)/drafts/[id]/page.tsx`, 254 lines)

**Strengths:** Two-column layout (editor 2/3, side panel 1/3). Generation metadata side panel surfaces the citations count (208-218) — this is the trust evidence and it's visible. Status-flow workflow (`STATUS_FLOW` map at 33-38) drives "Mark reviewed → Mark submitted" buttons that progress the user.

**Drift / friction:**
- **The big save button** is `bg-neutral-900` (172). Submit-mark button is `bg-emerald-600` (108). Export-DOCX button is `bg-brand-700` (96). Three primary actions, three different colors. None of them consistent with each other.
- **The textarea has no markdown preview.** Drafters edit in raw markdown only. (Out of scope per CLAUDE.md §3 — domain rewrites — but worth flagging.)
- **`PageHeader` is used correctly here** — eyebrow includes version + draft type, subtitle inline-renders status badge + notice type + opp title.
- **Citations are shown as raw counts** (210-217) — "Capabilities cited: 3" — without any path to "which 3?" Trust requires being able to follow the citation back.
- **No `Term` wrap on the type strings** ("Sources Sought", "rfp_response", "compliance_matrix") in the eyebrow.

**"What should I do here?"** answer: clear (edit, save, mark, export). The status-flow buttons + metadata panel + regenerate panel give the user the right verbs. Score: **7/10**.

### `/forecasts` (`apps/web/app/(app)/forecasts/page.tsx`, 189 lines)

**Strengths:** Page subtitle (66-74) names the data sources (DHS APFS, VA FCO, USACE, AFBES, GSA, HHS) — credibility move. Filter for "your NAICS" vs "all." Card layout consistent with other domain lists.

**Drift / friction:**
- **No Term wraps anywhere.** "Procurement forecasts", "Set-aside", "POP", "RFP expected", "Federal footprint", "Apify" — all bare.
- **"target NAICS" pill** (118-120) uses `bg-brand-50 text-brand-800` raw — should be `bg-primary/10 text-primary`.
- **Empty state** (96-102) bypasses `<EmptyState>` entirely and goes straight to `<IntegrationDiagnostic>`. That component (`components/integration-diagnostic.tsx`) is an ops surface — it shows worker-run status and a "trigger now" button. For the four founders this is fine; for a Phase 4+ external customer, this would expose internal scheduler details. Should wrap in an `<EmptyState>` first, with `<IntegrationDiagnostic>` as an admin-fold-out.
- **`text-amber-700`** literal (148) for "RFP expected" highlight — should be `text-warning`.
- **No keyboard-list navigation.**

**"What should I do here?"** answer: muddled. The page subtitle says what forecasts are; the value is there; but each card is a wall of text + chips with no clear "what should I do with this?" affordance. Score: **5.5/10**.

### `/recompetes` (`apps/web/app/(app)/recompetes/page.tsx`, 357 lines)

**Strengths:** Purpose-built for the highest-leverage signal in CaptureOS — "every forecast where we know the incumbent." Dense filter strip (114-169) with set-aside scope, agency, POP window, and a "Mine" toggle for the logged-in founder. Incumbent block (251-298) shows ticker, distress score, contract end, federal footprint, SEC filings — this is real intelligence.

**Drift / friction:**
- **EMOJI VIOLATION.** Line 261: `🚩 distress {fc.incumbent_distress_score}`. CLAUDE.md §3 explicitly says no emoji in product UI. The flag emoji is here. **Must remove this pass.**
- **`bg-amber-50`, `bg-rose-200`, `text-amber-900`, `text-rose-900`** literals (250-263) — should be `bg-warning/10`/`text-warning` and `bg-destructive/20`/`text-destructive`. Even more important now that we have semantic tokens.
- **POP, EDGAR, SEC, distress** — all bare jargon. "POP" especially needs a Term wrap; a small DIB contractor can guess it means period of performance, but that's exactly the kind of expert assumption CaptureOS prides itself on not making.
- **Filter strip is full-width and wraps** (110-169). Three filter axes (set-aside, agency, POP, lane) are flat with no grouping. On 1024 wide it wraps to four lines. Hard to scan.
- **"target NAICS" pill** uses `bg-brand-50 text-brand-800` raw — same as forecasts.
- **Card structure** is identical to forecasts but with the incumbent block injected. The duplication is fine; the visual divergence between them is also fine. But neither uses the new shadcn `Card` family.

**"What should I do here?"** answer: clear if you understand recompetes. The page subtitle teaches well. For a layman: "what's a recompete?" is answered, but "what do I do with one?" isn't. Each card needs a "Position now" or "Plan capture" affordance. Score: **6.5/10** (would be 7+ once the emoji is gone and POP/EDGAR are wrapped).

### `/events` (`apps/web/app/(app)/events/page.tsx`, 135 lines)

**Strengths:** Short and focused. Page subtitle names sources (DoD OSBP, NIWC, AFCEA, GSA OSDBU, DHS S&T, AFLCMC, Army OSBP) — credibility. Card with kind / agency / dates / location / NAICS / register button.

**Drift / friction:**
- **Empty-state body sends user to `/forecasts` to "check the diagnostic"** (45-50) — ops voice. Should say "there are no upcoming industry days yet — try widening your filter, or check back in a day" and offer a check-back affordance.
- **No Term wraps.** "Industry day", "Pre-solicitation", "OSBP", "Meet the buyer", "Symposium" — bare.
- **`code` block** at line 128-130: ``mactech_workers.tasks.apify_industry_days`` — this is internal worker name leaking into the UI. A layman would have no idea what it means. Should be a comment, not user-visible.
- **Register button is full brand teal** (97-100) — the only page where the primary action is unambiguously brand teal. Good. But the pattern hasn't been propagated.

**"What should I do here?"** answer: clear (look, register). Score: **7/10** — small page, fewer drift opportunities; the only thing keeping it from 8 is the worker-name leak and the no-jargon-help.

### `/settings` (`apps/web/app/(app)/settings/page.tsx`, 260 lines)

**Strengths:** Three-section structure: Tenant / Founders / Saved searches / NAICS matrix. Pillar chips on each founder. NAICS matrix is a clean table with primary/secondary tier badges.

**Drift / friction:**
- **Eyebrow says "Read-only for Phase 2 Week 6. Editing UIs ship in later phases."** (16) — internal sprint-numbering language leaking into the UI. A layman wouldn't know what "Phase 2 Week 6" means. Should be a soft-disabled state with a "edit coming soon" microcopy.
- **No `Term` wraps.** "UEI", "CAGE", "Clerk org", "tier: primary", "tier: secondary", "saved searches", "alert threshold", "alert cadence", "alert channels", "NAICS matrix" — all bare.
- **`tone="blue"` for primary tier and `tone="neutral"` for secondary** (211-212). Why blue? The semantic system supports `tone="brand"` which would make primary-NAICS visually obvious. Currently a non-semantic choice.
- **The NAICS table has no row hover, no link to filter opportunities by that NAICS, no link to the SBA size-standard lookup.** It's a static table. For a tenant-admin a quick "filter opportunities by 541512" link would multiply the value.

**"What should I do here?"** answer: muddled. "Read-only" + "Editing UIs ship in later phases" tells the user there's nothing to do; but "+ Add founder" link in the Founders section (52-57) is an exception that contradicts the eyebrow. Mixed signals. Score: **5.5/10**.

### `/onboarding` (`apps/web/app/(app)/onboarding/page.tsx`, 400 lines)

**Strengths:** Two-minute promise in subtitle (90-94). SAM.gov auto-fill on UEI lookup. Set-aside checkbox grid with hint per option (`SET_ASIDE_OPTIONS` 12-29). NAICS picker with primary/secondary tier separation.

**Drift / friction:** Out of scope for this pass — onboarding is a separate journey and the brief lists it as one of the 12 routes but it functions more like an "auth-adjacent" page than an in-product page. **Quick observations only:**
- The set-aside hint dictionary (13-29) is the most consistent jargon-help pattern in the app — this is what `Term` should look like everywhere.
- Page subtitle has the "later sprint" leak ("NAICS picker and founder roster ship in a follow-up sprint" — line 92-94).

Score: **7.5/10**.

---

## 3. The "layman DIB contractor" lens

The CLAUDE.md §1 + §8 user is not a Beltway BD professional. They're either Brian/John (founders less code-oriented) or — Phase 4+ — a 12-person SDVOSB defense subcontractor where one person wears the CO/PM/BD/sales hat. They open CaptureOS to find work and stay eligible for it. Three buckets of friction emerge from the per-page audit:

### Words that assume insider knowledge (used bare on at least one in-scope page)

`POP`, `POP-end`, `period of performance`, `Section L`, `Section M`, `SOW`, `PWS`, `RFI`, `RFP`, `Sources Sought`, `pre-solicitation`, `combined synopsis`, `set-aside`, `NAICS`, `UEI`, `CAGE`, `SPRS`, `CMMC`, `DFARS`, `FAR`, `8(a)`, `HUBZone`, `WOSB`, `EDWOSB`, `SDVOSB`, `JV`, `prime`, `sub`, `joint venture`, `incumbent`, `recompete`, `discriminator`, `win theme`, `compliance matrix`, `requirements matrix`, `evaluation factors`, `embedded` (vector embedding), `vector match`, `cosine similarity`, `OSBP`, `ATO`, `RMF`, `ConMon`, `STIG`, `eMASS`.

The `Term` system already explains a portion of these (notice types, set-aside certs, NAICS, SPRS, FAR/DFARS clauses). Coverage is concentrated on opportunity detail / pursuit detail / solicitation-panel / cyber-posture-card / tenant-eligibility-card. Coverage is **near-zero on**: `/pipeline` stage labels, `/library` section labels, `/drafts` type/status labels, `/forecasts` value/POP labels, `/recompetes` POP/EDGAR/distress labels, `/events` kind labels, `/settings` tenant fields.

### Dashboards that bury the lede

The dashboard's lede is `TodaysMoves` — that's correct. But the `HowItWorks` block (524 lines into the file, 3-step explanation) is BELOW the four KPIs and the `your_top` list. A first-time visitor sees four numbers, then a list of opportunities, then the "this is how the product works" block. The right ordering is: greeting → "this is how it works" (collapsible) → today's moves → KPIs → your top. Currently it's: greeting → KPIs → today's moves → how it works → your top.

### Empty states that leave the user lost

- `/forecasts` empty state goes straight to `<IntegrationDiagnostic>` — ops surface. Layman thinks the product is broken.
- `/events` empty state says "check the diagnostic on /forecasts" — sends the user to a different page to debug.
- `/drafts` empty state says "Find Sources Sought opps" — better but assumes the user knows what Sources Sought is.
- `/pipeline` first-time pedagogical 3-step is **the exemplar** — `library/page.tsx`'s three EmptyStates approach this. Everywhere else falls short.

### Errors that aren't actionable

The page-level error overlay isn't in scope (it's Next.js's). But several pages handle backend errors by silently `.catch(() => null)` and rendering an empty state — `forecasts/page.tsx:44-53` for integrations, `dashboard/page.tsx:42-80` for events/recompetes/forecasts/eligibility, etc. The user sees "no events" when the actual cause is "events ingester crashed." We can't fix the silent-catch this pass without rewriting the data-fetch layer, but we should at least surface a "couldn't load — retry" affordance on the empty states.

---

## 4. Cross-cutting gaps (the system, not any one page)

### Shell shape consistency
- ✅ Sidebar / topbar / main / footer mounts uniformly via `(app)/layout.tsx`.
- ❌ Sidebar nav uses `border-brand-700 bg-brand-50 text-brand-900` legacy literals (`sidebar-nav.tsx:82`) — should be `border-primary bg-primary/10 text-foreground` (or a dedicated `--sidebar-active` token).
- ⚠️ Topbar (line 81-98 of layout) shows tenant name + plan badge + Clerk UserButton. The plan badge is uppercase tracking-wider; the tenant name is bold — fine. The Clerk UserButton renders Clerk-default styling regardless of our tokens; pre-existing.

### `PageHeader` consistency
- ❌ Used in 11 of 12 in-scope routes; opportunity detail rolls its own. Should adopt the primitive.
- ❌ `display={true}` is used on opportunity detail (rolled-its-own) + pursuit detail + capture-package + dashboard's `display=false size="sm"`. Three semantic uses of one prop. The rule should be: **decision/work surfaces** (opportunity detail, pursuit detail, capture-package) use `display`; **catalogue surfaces** (opportunities list, library, drafts list, settings) use default sans; **conversational surfaces** (dashboard greeting) use `size="sm"`.

### `Section` / `Card` rhythm
- The repo has both `Section` (borderless titled section) and `Card` (boxed white card) in `ui.tsx`. They're used appropriately on the dashboard. Other pages use raw `<section className="rounded-md border ...">` instead of either primitive — see `forecasts/page.tsx`, `recompetes/page.tsx`, `pipeline/page.tsx`, `pursuits/[id]/page.tsx`. Migrating to `<Card>` collapses ~30 inline className strings to a single primitive.
- The new shadcn `Card` family in `components/ui/` is unused. Either migrate to it or document it as legacy-only.

### `Kpi` strip pattern
- Dashboard is the only page that uses `<Kpi>` (4 callsites). Library has its own `SummaryStat` (lines 513-531) — visually identical to `Kpi` but renamed. Should consolidate.
- `Kpi` sets `tabular-nums` on values; `SummaryStat` does too. Both opt-in to the same body-level tabular-nums declared in globals.css.

### Breadcrumb / back-affordance pattern
- Three different patterns in three places (opportunity detail, pursuit detail, draft detail). No standard. Add a `<BackLink>` primitive — `← All opportunities` shape, accepts an href + label, sits above `<PageHeader>` consistently.

### Primary-action affordance pattern
- Currently FOUR primary-action colors: `bg-neutral-900` (black, on opportunity list, library, pipeline, settings), `bg-brand-700` (teal, on capture-package, sign-in, marketing landing, draft export), `bg-amber-700` (onboarding nudge), `bg-emerald-600` (won marker, mark-submitted). Resolution: brand-teal `--primary` is the only primary; everything else is a semantic variant (`--success`, `--warning`, `--destructive`).
- The shadcn `<Button variant="primary">` in `components/ui/button.tsx` already maps to `bg-primary text-primary-foreground`. Migrating the 30+ inline button instances to that variant resolves the entire ambiguity in a single PR.

### Error / empty-state pattern
- `<EmptyState>` is used on 6 of 12 routes. `/forecasts` and `/events` skip it. Standardize: every list page that can be empty MUST mount `<EmptyState title body action>` and never just render the content area empty.
- Body should explain (a) why it's empty, (b) what would change that, (c) one action. The current `<EmptyState>` API supports that but isn't enforced.

### Mobile responsive posture
- Dashboard, opportunities list, opportunity detail collapse cleanly to single-column at <md.
- Pipeline horizontal-scrolls at <lg via `min-w-[1100px]` (line 114) — that's a deliberate choice that says "kanban is a desktop tool." Acceptable but should be documented.
- Pursuit detail's 11-section stack is the worst mobile experience in the app — needs a TOC or accordion for <lg.
- No page uses a mobile drawer for filters. `/opportunities` left filter sidebar stacks above results on <lg, pushing the first opportunity below the fold.

### Jargon-helper coverage
- **The single most undervalued asset in the app.** 52 callsites, but concentrated on 5 files. Six pages have zero coverage. The fix is mechanical: for every CMMC/SPRS/FAR/Section L/Section M/POP/SOW/PWS/RFI/RFP/Sources Sought/UEI/CAGE/NAICS string in JSX text, wrap it. Most are static strings — search-and-replace is safe.
- The `Term` taxonomy needs documenting (kinds list, naming convention) but that's a doc-task, not this pass.

---

## 5. Prioritized leverage points (architect picks 5–7 to ship)

Ranked strictly by impact / effort. Each item is implementable as a single focused PR; the architect should pick from the top.

### 1. **Unify primary-action color across every authenticated page.**
- Problem: Four different "primary" button colors in active use (`bg-neutral-900`, `bg-brand-700`, `bg-amber-700`, `bg-emerald-600`). User can't learn the rule.
- Evidence: `dashboard/page.tsx:154`, `opportunities/[id]/page.tsx:521`, `pipeline/page.tsx:72`, `library/page.tsx:97/213/333`, `settings/page.tsx:53`, `pursuits/[id]/page.tsx:231/473/611`, `drafts/[id]/page.tsx:107/170` — black-button "primary" is the dominant pre-tokenization pattern. Brand-teal "primary" is the post-tokenization pattern.
- Proposed direction: every primary action (the one CTA per surface) becomes `<Button variant="primary">` from `components/ui/button.tsx` — which already resolves to `bg-primary text-primary-foreground`. Won/Lost/Submitted markers use semantic variants (`success`/`destructive`). Black `bg-neutral-900` deletes from the codebase except inside Cmd-K (its dialog chrome).
- Impact: **High** — visible on every page. Makes the brand decision visible.
- Effort: **M** — ~30 callsites to migrate, but the `<Button>` component already exists.
- Files: every in-scope page (mechanical search-and-replace).

### 2. **Wrap every bare jargon string with `<Term>` or `<TermPopover>` on the six low-coverage pages.**
- Problem: `Term`/`TermPopover`/`ExplainRail` is the strongest brand differentiator, but six pages have near-zero coverage.
- Evidence: `pipeline/page.tsx` (stage labels Lead/Qualify/Pursue/Propose/Submit), `library/page.tsx` (capability statements / past performance / teaming partners / embedded / NAICS coverage), `drafts/page.tsx` (Sources Sought / RFP response / compliance matrix / status flow), `forecasts/page.tsx` (POP / RFP / target NAICS), `recompetes/page.tsx` (POP / EDGAR / SEC / distress / set-aside scope), `events/page.tsx` (Industry day / Pre-solicitation / OSBP), `settings/page.tsx` (UEI / CAGE / Clerk org / tier primary/secondary).
- Proposed direction: for each bare jargon string in JSX text, wrap it with `<Term kind="..." value="...">label</Term>`. Use existing `kind`s where possible (`section`, `clause`, `cmmc`, `sprs`, `naics`, `set_aside`, `set_aside_cert`); add new ones for `pursuit_stage`, `draft_type`, `draft_status`, `pop`, `incumbent_distress`, `tenant_field` (UEI/CAGE), `library_section` (capability/past-perf/teaming).
- Impact: **High** — directly serves the layman audience the user named in this brief. Brian and John can read every page.
- Effort: **M** — mostly mechanical wrapping, but new `kind`s require backend `/explain/{slug}` entries (the LLM auto-generates these on demand and caches; one-time cost).
- Files: six pages above; `lib/api.ts` (no change needed if backend auto-generates); optionally `docs/DESIGN_SYSTEM.md` to document `Term` taxonomy.

### 3. **Migrate to a single pursuit-stage tone map and remove emoji from `/recompetes`.**
- Problem: Three different pursuit-stage palettes in three files; emoji in `/recompetes` violates voice.
- Evidence: `pipeline/page.tsx:50-58`, `opportunities/[id]/page.tsx:468-476`, `pursuits/[id]/page.tsx:50-58` — three different `STAGE_TONE` maps. `recompetes/page.tsx:261` — `🚩 distress`.
- Proposed direction: extract `STAGE_TONE`/`STAGE_LABEL` into `lib/pursuits.ts` (or `components/domain/pursuit.tsx`), import everywhere. Replace `🚩` with a `<Badge tone="red">distress {n}</Badge>` or text-only `distress signal: {n}` — semantics over decoration.
- Impact: **High** — emoji removal is a hard voice-rule violation; tone-map unification gives the user one mental model of the lifecycle.
- Effort: **S** — ~5 files touched, all mechanical.
- Files: `lib/pursuits.ts` (new export), `pipeline/page.tsx`, `opportunities/[id]/page.tsx`, `pursuits/[id]/page.tsx`, `recompetes/page.tsx`.

### 4. **Replace the inline opportunity-detail header with `<PageHeader display>` + extract `<BackLink>` primitive.**
- Problem: Opportunity detail is the flagship page and it doesn't use `PageHeader`. Three different back-affordance patterns across detail pages.
- Evidence: `opportunities/[id]/page.tsx:152-229` rolls its own header. `pursuits/[id]/page.tsx:208-243` uses PageHeader. `drafts/[id]/page.tsx:60-74` uses two top links.
- Proposed direction: convert the opportunity-detail header to `<BackLink href="/opportunities">All opportunities</BackLink>` + `<PageHeader display eyebrow={agency} title={title} subtitle={chip-row} trailing={score+open-on-sam}>`. Add `<BackLink>` primitive in `components/ui.tsx` — accepts href + label, renders the standard `← {label}` shape with `text-xs text-muted-foreground hover:text-foreground`.
- Impact: **Medium** — matches the rest of the app on the most-loved page; reduces template duplication.
- Effort: **S** — `BackLink` is 10 lines; opp-detail header reshape is ~30 lines.
- Files: `components/ui.tsx` (add `BackLink`), `opportunities/[id]/page.tsx` (replace inline header), `pursuits/[id]/page.tsx` (use new BackLink), `drafts/[id]/page.tsx` (use new BackLink).

### 5. **Standardize `<EmptyState>` adoption — every list page mounts it; pedagogical voice mandatory.**
- Problem: `/forecasts` and `/events` skip `EmptyState` and inline ops-tone fallback. Empty-state voice quality is uneven.
- Evidence: `forecasts/page.tsx:96` (renders `<IntegrationDiagnostic>` directly when empty), `events/page.tsx:37` (uses EmptyState but body sends user to forecasts diagnostic), `drafts/page.tsx:39` (correct), `library/page.tsx` (correct), `recompetes/page.tsx:193` (correct).
- Proposed direction: every empty list mounts `<EmptyState title body action>`. Body teaches: (a) what the page would normally show, (b) what would put data here, (c) one CTA. For `/forecasts` and `/events`, the diagnostic surface lives behind a `<details>Admin diagnostic</details>` fold-out, not the primary empty state.
- Impact: **Medium** — every empty page becomes the user's chance to learn.
- Effort: **S** — ~3 pages to fix.
- Files: `forecasts/page.tsx`, `events/page.tsx`, `drafts/page.tsx` (voice tweak only).

### 6. **Migrate hot pages off legacy palette literals to tokens.**
- Problem: 497 legacy palette hits in `app/(app)/`. Two parallel color systems are running. Future cross-suite ports cost double.
- Evidence: 37 hits in dashboard + pipeline + opp-detail alone (the three hottest files). Examples: `border-paper-200`/`bg-paper-50`/`bg-white`/`text-neutral-500`/`text-brand-700`/`bg-brand-700`.
- Proposed direction: scoped find-and-replace per file, in this order: dashboard → pipeline → opp-detail → opp-list → pursuits-detail → drafts → library → forecasts → recompetes → events → settings. Mapping: `bg-white` → `bg-card`; `border-paper-200` → `border-border`; `bg-paper-50` → `bg-secondary`; `text-neutral-500` → `text-muted-foreground`; `text-brand-700` → `text-primary`; `bg-brand-700` → `bg-primary`; `bg-brand-50` → `bg-primary/10`; `bg-amber-50` → `bg-warning/10`; `text-amber-700` → `text-warning`; `bg-emerald-600` → `bg-success`; `bg-red-600` → `bg-destructive`; `border-red-300` → `border-destructive/40`; `border-amber-300` → `border-warning/40`. Legacy aliases in `tailwind.config.ts` stay during migration; remove in a follow-up.
- Impact: **Medium** (long-term: high) — visually invisible to users; massive payoff for cross-suite portability.
- Effort: **L** if all 12 pages, **M** if just the top 3 hot pages.
- Files: every in-scope page (recommend top 3 this pass, rest next).

### 7. **Add a `<Section>`-based in-page nav to `/pursuits/[id]` (the 11-section scroll).**
- Problem: Pursuit detail is the deepest-work surface in the app — 11 stacked sections — with no in-page navigation.
- Evidence: `pursuits/[id]/page.tsx:200-320` — sections stack vertically with no jump-list.
- Proposed direction: at `lg+`, render a sticky-left mini-TOC ("Bid decision · Notes · Win strategy · Amendments · Solicitation · Past performance · Key personnel · Teaming partners · Agency intel · Web mentions · Audit · Danger zone"). At <lg, the same list as a collapsible accordion at the top. Each section gets an id + `scroll-mt-24` for header offset.
- Impact: **Medium** — biggest QoL improvement for the 4 founders' daily workflow.
- Effort: **M** — ~50 lines of new component, every section gets an id.
- Files: `pursuits/[id]/page.tsx` (mostly), `components/ui.tsx` (optional `<SectionAnchor>` primitive).

### 8. **Promote the dashboard's `HowItWorks` above-the-fold for first-time users; demote for return users.**
- Problem: The 3-step "how CaptureOS works" block is below the KPI strip — first-time users see 4 numbers before they see the 3-step explanation.
- Evidence: `dashboard/page.tsx:484-527` — `HowItWorks` mounted after `your_top` list. Cookie-based dismiss (`HOW_IT_WORKS_COOKIE`).
- Proposed direction: when the cookie is unset (first session), render `HowItWorks` directly under the greeting and above the KPIs. When dismissed or after the user has any pursuit, mount it where it is now (or hide entirely). Add a "Start tour" affordance somewhere to bring it back manually.
- Impact: **Medium** — Phase 4+ external users; less impact for the 4 founders.
- Effort: **S** — reorder a JSX block conditionally.
- Files: `dashboard/page.tsx`.

### 9. **Add semantic-token migration to the `Pipeline` aging colors and `TodaysMoves` tone map.**
- Problem: Pipeline aging hardcodes `border-amber-300`/`border-red-300`/`text-amber-700`/`text-red-700`. TodaysMoves has its own ad-hoc tone map.
- Evidence: `pipeline/page.tsx:239-254`, `todays-moves.tsx:213-219`.
- Proposed direction: `border-warning/40`/`border-destructive/40`/`text-warning`/`text-destructive`. `TodaysMoves` tone tokens map to `--warning`/`--primary`/`--muted`.
- Impact: **Low / cumulative quality** — visually unchanged but contractually clean.
- Effort: **S**.
- Files: `pipeline/page.tsx`, `components/todays-moves.tsx`.

### 10. **Consolidate `library/page.tsx`'s `SummaryStat` into the existing `Kpi` primitive and migrate `<section className="rounded-md border ...">` callsites to `<Card>`.**
- Problem: Two visually-identical primitives doing the same job (`Kpi` and `SummaryStat`); inline `<section>` rounded-borders proliferating.
- Evidence: `library/page.tsx:513-531` defines `SummaryStat`; `forecasts/page.tsx:108`, `recompetes/page.tsx:217`, `pipeline/page.tsx:165`, `pursuits/[id]/page.tsx:multiple`, `dashboard/page.tsx:650` all roll their own card-shaped section.
- Proposed direction: `Kpi` is the single source for label + big number + hint. `Card` (existing legacy primitive) is the single source for boxed sections. Inline rounded-border `<section>` blocks migrate to `<Card>` or `<Card title=...>`.
- Impact: **Low** — long-term tidy.
- Effort: **M** — touches many files.
- Files: `library/page.tsx`, `forecasts/page.tsx`, `recompetes/page.tsx`, `pipeline/page.tsx`, `pursuits/[id]/page.tsx`, `dashboard/page.tsx`.

### 11. **Wire the inline-button proliferation across detail pages to `<Button variant>`.**
- Problem: ~25 inline buttons across opportunity-detail and pursuit-detail re-implement the shadcn Button shape.
- Evidence: `opportunities/[id]/page.tsx:519-528, 642-678`, `pursuits/[id]/page.tsx:404-410, 471-478, 547-554, 609-616, 657-664`. Each one is a hand-laid `rounded-md bg-X px-Y py-Z text-color`.
- Proposed direction: migrate all to `<Button variant="primary|secondary|ghost|destructive|success">` from `components/ui/button.tsx`. Add `success` and `warning` variants if missing.
- Impact: **Medium** — cleaner code; consistent focus rings; one-place style updates.
- Effort: **M** — careful migration to preserve focus / hover semantics.
- Files: `opportunities/[id]/page.tsx`, `pursuits/[id]/page.tsx`, `pipeline/page.tsx`, `library/page.tsx`, possibly all forms.

### 12. **Add a "primary affordance" to recompete cards: `Plan capture →` button.**
- Problem: `/recompetes` shows the highest-leverage signal in the product (named incumbent + POP-end) but has no affordance to act on it.
- Evidence: `recompetes/page.tsx:215-352` — each card has a "Source" link (out to the agency forecast page) and that's the only action.
- Proposed direction: add a "Plan capture" button on each card that links to a new (or existing if forecast is in opps) opportunity, OR adds the recompete to a watchlist that surfaces on the dashboard. (If the data model doesn't yet support a recompete-watchlist, the simpler version is to link to `/forecasts?incumbent={name}` for now.)
- Impact: **Medium** — turns a passive page into an active one.
- Effort: **M-L** — depends on whether the watchlist feature exists; might require a new endpoint.
- Files: `recompetes/page.tsx`, possibly `lib/api.ts`, possibly backend.

---

## 6. What to AVOID this pass

- **Do NOT port clearD's `cleard-hero-bg` radial-glow auras to any authenticated page.** That utility belongs to clearD's marketing surface; CaptureOS cards stay opaque and document-feel. (Brief 1, §6 already rejected this; reaffirming.)
- **Do NOT introduce dark mode.** The light-first warm-paper decision is locked.
- **Do NOT switch primary teal to copper or any other color.** Brand-teal `#207b78` (resolved through `--primary`) is the decision.
- **Do NOT rewrite the domain cards listed in the constraint** (`agency-intel-card.tsx`, `cyber-posture-card.tsx`, `solicitation-panel.tsx`, `audit-trail-card.tsx`, `ask-streaming.tsx`, `draft-streaming.tsx`). Token migrations transparent to them are fine; layout changes are not.
- **Do NOT add decorative iconography** (Lucide icons, brand-mark chips, illustrated empty states). The product is editorial and direct; iconography is reserved for functional affordances (Cmd-K, ?, ✕, ↻, →, ↑, ↓ — typographic or single-glyph).
- **Do NOT introduce glassmorphism / backdrop-blur** on dashboard cards. Cards stay opaque.
- **Do NOT marketing-frame the copy.** No "powerful," no "easy-to-use," no "designed for the modern federal contractor." Sober, plainspoken, competent.
- **Do NOT remove the `font-serif` italic display titles** on opportunity / pursuit / capture-package. Brand DNA.
- **Do NOT widen scope to onboarding wizard or capture-package detail page** unless the architect has bandwidth — those are separate journeys. Brief 1's §8 non-goals still apply.
- **Do NOT import any emoji as decorative element.** The 🚩 violation in `/recompetes` is the example of what to avoid (and remove).
- **Do NOT touch the footer color decision.** Brief 1's reversal locked it as obsidian for cross-suite continuity.

---

## 7. Section 9: Success criteria for the verifier

The architect's PR for this iteration succeeds if all of the following are true:

1. **Single primary-action color in the app.** `grep -nE "bg-neutral-900|bg-amber-700|bg-emerald-600|bg-red-600" apps/web/app/\(app\) -r` returns zero hits in JSX class strings (matches in tone-record values are OK only if the value resolves to `bg-success`/`bg-warning`/etc). Every primary CTA on every authenticated page mounts `<Button variant="primary">` (or matches that styling).
2. **Every authenticated page mounts `<PageHeader>`.** Specifically: opportunity detail (`opportunities/[id]/page.tsx`) replaces its inline header with `<PageHeader display>` + `<BackLink>`. Verify with `grep -L "<PageHeader" apps/web/app/\(app\)/*/page.tsx apps/web/app/\(app\)/*/\[id\]/page.tsx` — empty output.
3. **`<BackLink>` exists as a primitive** (`components/ui.tsx` or `components/ui/back-link.tsx`) and is used on opportunity detail, pursuit detail, draft detail (3 callsites minimum). No two detail pages have different back-affordance shapes.
4. **No emoji in any non-error UI string.** `perl -ne 'print if /[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]/' apps/web/app/\(app\) apps/web/components -r` returns zero matches. The 🚩 in `/recompetes` is gone.
5. **Single `STAGE_TONE` and `STAGE_LABEL` source.** Exported from `lib/pursuits.ts` (or `components/domain/pursuit.tsx`); imported by pipeline, opportunity-detail, pursuit-detail. `grep -c "STAGE_TONE.*Record" apps/web/app/\(app\) -r` = 0 (no per-file redefinitions).
6. **Bare jargon coverage.** On every surface touched this pass, the following words MUST be wrapped in `<Term>` or `<TermPopover>` at least on first occurrence per page: `POP`, `Section L`, `Section M`, `SOW`, `PWS`, `Sources Sought`, `RFP`, `RFI`, `set-aside`, `NAICS`, `UEI`, `CAGE`, `SPRS`, `CMMC`, `DFARS`, `FAR`, `SDVOSB`, `8(a)`, `HUBZone`, `WOSB`, `EDWOSB`, `JV`, `pursuit stage` labels (`Lead`/`Qualify`/`Pursue`/`Propose`/`Submit`/`Won`/`Lost`), `embedded`, `vector match`, `incumbent distress`. Verifier spot-check: open `/pipeline`, `/library`, `/drafts`, `/forecasts`, `/recompetes`, `/events`, `/settings` — every page has at least 3 `<Term>` callsites.
7. **`<EmptyState>` mounted on every empty-able list page.** `/forecasts` and `/events` empty surfaces use `<EmptyState>`; `<IntegrationDiagnostic>` lives behind a `<details>` fold-out or after the EmptyState, not in place of it.
8. **No legacy-palette literals on the three hot pages.** `grep -nE "bg-paper-|border-paper-|text-brand-|bg-brand-|border-brand-|text-neutral-(?!200)" apps/web/app/\(app\)/dashboard/page.tsx apps/web/app/\(app\)/pipeline/page.tsx apps/web/app/\(app\)/opportunities/\[id\]/page.tsx` returns zero hits in JSX class strings (legacy in comments / type-record-keys allowed).
9. **Pursuit-detail in-page nav present at `lg+`.** Sticky left rail or sticky top accordion linking to the 11 sections by anchor. Every section has a stable `id`.
10. **Sidebar active-state uses tokens.** `sidebar-nav.tsx:82` no longer uses `bg-brand-50 border-brand-700 text-brand-900`; uses `bg-primary/10 border-primary text-foreground` (or equivalent token).
11. **No emoji, no marketing-frame copy, no `bg-[#xxxxxx]` literals introduced.** (Carry-over from Brief 1.)
12. **No `dark:` Tailwind variants introduced.** (Carry-over.)
13. **`Term` taxonomy documented somewhere.** Either `docs/DESIGN_SYSTEM.md` or `apps/web/components/README.md` lists the supported `kind`s with examples.
14. **Mobile horizontal-scroll regression check.** `/dashboard`, `/opportunities`, `/opportunities/[id]`, `/pipeline`, `/pursuits/[id]`, `/library`, `/drafts`, `/drafts/[id]`, `/forecasts`, `/recompetes`, `/events`, `/settings` at 375 / 768 / 1024 / 1440 — no horizontal scroll except `/pipeline` (which has explicit `min-w-[1100px]` for the kanban grid).
15. **Contrast spot-check.** `text-warning` on `bg-card` ≥ 3:1 (passes for badges); `text-destructive` on `bg-card` ≥ 4.5:1 (passes for body); `text-muted-foreground` on `bg-secondary` ≥ 4.5:1.

---

## 8. Section 10: Open questions for the human

1. **Of the 12 in-scope routes, which 3 most matter to lift in this single pass?** My recommendation, ranked by user-value-per-effort: (a) `/dashboard` (it's the everyday landing, and the legacy-palette holdouts + how-it-works ordering + ComingUpRail tokenization are all medium-effort fixes), (b) `/opportunities/[id]` (flagship surface, biggest payoff for the layman audience — `<PageHeader>` adoption + `<Button variant>` migration + score-rationale promotion), and (c) `/pursuits/[id]` (the deep-work surface where the founders spend the most time — in-page nav alone is a meaningful lift). If only 2 can ship, drop pursuit detail. If only 1, ship `/opportunities/[id]` — it's the page everyone enters CaptureOS through.
2. **Are we OK migrating dashboard / pipeline / opportunity-detail from `components/ui.tsx` (legacy 589-line file) to the new shadcn primitives this pass?** The shadcn Button/Card/Badge are scaffolded but unused. My recommendation: migrate the three hot pages' button instances ONLY to `<Button>` (leverage point #1 + #11) — a single mechanical migration. Leave Card/Badge migration for a follow-up; they're more tangled with domain components like `ScoreBadge`/`Pillar`/`NaicsBadge`. The legacy `ui.tsx` file stays.
3. **Pursuit-stage labels — are they brand-stable?** `Lead`/`Qualify`/`Pursue`/`Propose`/`Submit`/`Won`/`Lost` is a 7-stage pipeline. For a layman SDVOSB owner, `Pursue` and `Propose` are easy to confuse. Should the labels rename to something more vernacular (e.g. `Watching` / `Researching` / `Capturing` / `Drafting` / `Submitting` / `Won` / `Lost`)? Or are these the BD-canonical names that an external customer in Phase 4 will recognize and we shouldn't fork? My instinct: keep the names, add `<Term>` wraps with plain-English explanations. Confirm.
4. **Recompete `Plan capture` action — does the data model support a "recompete watchlist" yet, or is it a dashboard nudge / link to `/forecasts?incumbent={name}` for now?** Leverage point #12 depends on this. If the watchlist doesn't exist, the simpler "filter forecasts by incumbent" link is the right Phase 1 move.
5. **Is the topbar tenant-name + plan-badge surface load-bearing?** It's tiny chrome (line 81-98 of layout). For a 4-founder Phase 1 product, it's cosmetic. For a Phase 4 multi-tenant external customer, it's important. Should we invest in making it a tenant-switcher (so users with multiple tenants — e.g. a CaptureOS admin) can swap), or keep it as static chrome this pass?

---

## 11. Human responses (auto-mode decisions)

Auto mode active — answers chosen by the orchestrator from CLAUDE.md context, the brief, and the user's instruction "perform a complete suite continuity and UX/UI upgrade for captureOS all internal pages should be worldclass UX/UI fit for a layman DIB contractor to succeed":

1. **Top 3 routes to lift this pass.** Take the researcher's ranking: `/opportunities/[id]` (flagship — every user enters here), `/dashboard` (the daily landing), `/pursuits/[id]` (deep-work surface). The user said "all internal pages" — interpret that ambition as: the cross-cutting fixes (primary-action color, jargon coverage, emoji removal, EmptyState standardization, sidebar token, single STAGE_TONE) hit *every* page; the per-page deep-lifts focus on these three. Other pages get the cross-cutting wins for free.
2. **Shadcn Button migration on hot pages — yes, this pass.** Migrate every primary-action `<button className="bg-neutral-900...">` and `<button className="bg-brand-700...">` and `<button className="bg-amber-700...">` and `<button className="bg-emerald-600...">` and `<button className="bg-red-600...">` to `<Button variant>` from `@/components/ui/button`. Keep `Card`/`Badge` shadcn migration scaffolded but unused — it tangles with `ScoreBadge`/`Pillar`/`NaicsBadge` domain components, defer.
3. **Pursuit-stage labels stay (`Lead`/`Qualify`/`Pursue`/`Propose`/`Submit`/`Won`/`Lost`).** Add `<Term kind="pursuit_stage" value="lead|qualify|...">` wraps with plain-English explanations. Don't rename — those are BD-canonical and external customers will recognize them.
4. **Recompete "Plan capture" action — defer.** No watchlist data model yet, and the link-to-forecasts-by-incumbent stopgap is enough work to push this pass over budget. Skip LP #12.
5. **Topbar tenant-switcher — defer.** Phase 1 has 4 known founders on one tenant; topbar stays static chrome.

**Architect's selected leverage points for this iteration (6 total)**:
- §5.1 — Unify primary-action color (every primary CTA → `<Button variant="primary">`)
- §5.2 — Jargon coverage with `<Term>` on the six low-coverage pages (`/pipeline`, `/library`, `/drafts`, `/forecasts`, `/recompetes`, `/events`, `/settings`) plus the dashboard KPI tiles
- §5.3 — Single `STAGE_TONE`/`STAGE_LABEL` source in `lib/pursuits.ts` + remove the 🚩 emoji from `/recompetes`
- §5.4 — `<BackLink>` primitive + replace `/opportunities/[id]` inline header with `<PageHeader display>`
- §5.5 — `<EmptyState>` standardization on `/forecasts` and `/events` (diagnostic surface goes behind a `<details>` fold)
- §5.6 — Token migration on the three hot pages only (dashboard, pipeline, opportunity-detail). Ship #4.10 sidebar token swap as part of this — it's the same kind of edit.

**Deferred for next pass (out of scope this iteration)**: §5.7 pursuit-detail in-page nav, §5.8 HowItWorks reordering, §5.9 broader semantic-token migration (covered partially by §5.6), §5.10 SummaryStat→Kpi consolidation, §5.11 broader button migration (covered partially by §5.1), §5.12 recompete plan-capture action.
