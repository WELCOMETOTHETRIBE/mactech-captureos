# Change Log
For brief: 2026-05-08T21:30:00-07:00
Iteration: 2
Generated: 2026-05-08T22:30:00-07:00

## Items addressed

### §5.1 — Unify primary-action color
- **Brief reference:** §5.1 + §7.1 + §11.2 (auto-mode answer: migrate `bg-neutral-900`, `bg-brand-700`, `bg-amber-700`, `bg-emerald-600`, `bg-red-600` button strings)
- **Files modified:**
  - `apps/web/components/ui.tsx` — extended legacy `Button` + `LinkButton` with `success` / `warning` / `destructive` variants and `size` prop (`default`/`sm`/`xs`); added `focus-visible:ring` to both for a11y.
  - `apps/web/app/(app)/dashboard/page.tsx` — onboarding-incomplete banner CTA → `LinkButton variant="warning"`; first-feed banner CTA → `LinkButton variant="primary"`.
  - `apps/web/app/(app)/pipeline/page.tsx` — `pillCls`, `StageBtn`, top-bar "Add from opportunities" link, FirstTimePipeline buttons all migrated; `StageBtn` switched to typed Button variants (`primary`/`success`/`destructive`).
  - `apps/web/app/(app)/opportunities/[id]/page.tsx` — `PursuitPanel`, `DetailStageBtn`, "Open kanban" link, "Generate brief", "Open latest draft" link all migrated.
  - `apps/web/app/(app)/opportunities/page.tsx` — facet-active pill `bg-neutral-900` → `bg-primary text-primary-foreground`.
  - `apps/web/app/(app)/pursuits/[id]/page.tsx` — Capture Package, Opportunity link, NotesEditor, WinStrategyEditor, Past Performance/Key Personnel/Teaming Partner Save buttons, Delete pursuit all migrated.
  - `apps/web/app/(app)/drafts/page.tsx` — empty-state CTA migrated.
  - `apps/web/app/(app)/drafts/[id]/page.tsx` — Export DOCX, Mark submitted (`success`), Save changes, Delete, Cancel — all migrated.
  - `apps/web/app/(app)/library/page.tsx` — every "+ Add cluster / Add record / Add partner / Import PDF" button migrated.
  - `apps/web/app/(app)/settings/page.tsx` — "+ Add founder" migrated.
  - `apps/web/app/(app)/recompetes/page.tsx` — chip-active class migrated to token form.
  - `apps/web/app/(app)/forecasts/page.tsx` — empty-state CTAs migrated.
  - `apps/web/app/(app)/events/page.tsx` — "Register" + empty-state CTAs migrated.
- **Approach taken:** introduce `success` / `warning` / `destructive` variants on the legacy `<Button>` (kept the existing `primary` / `secondary` / `ghost` / `danger`). Migrated every literal-styled action button on every authenticated page.
- **Design decisions worth flagging:**
  - The `danger` variant (outlined red border, card background) is preserved for "destructive but not the main action" — Delete buttons in detail-page footers. The new `destructive` variant is solid red, used only for terminal won/lost stage markers.
  - `LinkButton` got the same variants for consistency.

### §5.2 — Wrap bare jargon with `<Term>` / `<TermPopover>`
- **Brief reference:** §5.2 + §7.6
- **Files modified:**
  - `apps/web/app/(app)/pipeline/page.tsx` — full stage-glossary strip (Lead → Qualify → Pursue → Propose → Submit → Won · Lost) plus per-column header term wraps; 10 callsites total.
  - `apps/web/app/(app)/library/page.tsx` — section headers (capability_statements / past_performance / teaming_partners), "embedded" hint, NAICS coverage stat label, drafter section subtitle; 9 callsites.
  - `apps/web/app/(app)/drafts/page.tsx` — Sources Sought / RFP / compliance_matrix in subtitle, status + draft_type badges per row; 5 callsites.
  - `apps/web/app/(app)/drafts/[id]/page.tsx` — status + draft_type badges in PageHeader subtitle.
  - `apps/web/app/(app)/forecasts/page.tsx` — RFP, NAICS, set-aside in subtitle and per-card footer; 6 callsites.
  - `apps/web/app/(app)/recompetes/page.tsx` — NAICS, POP, set-aside (filter strip + cards), incumbent_distress (sec_ticker, score, edgar), RFP — 13 callsites.
  - `apps/web/app/(app)/events/page.tsx` — OSBP, industry_day, event_kind by row, NAICS — 4 callsites.
  - `apps/web/app/(app)/settings/page.tsx` — UEI, CAGE, saved_searches, NAICS, set_aside, NAICS matrix, NAICS tier badges — 8 callsites.
  - `apps/web/app/(app)/dashboard/page.tsx` — KPI glossary strip below the four tiles (high_fit, pursuit_stage overview, draft_type overview, score overview); plus UEI/CAGE on the setup banner and NAICS in first-feed-loading banner.
  - `apps/web/app/(app)/pursuits/[id]/page.tsx` — wrapped the existing stage badge in `<Term kind="pursuit_stage">`.
- **Approach taken:** list pages without the ExplainRail wired up use `<TermPopover>` (in-place popover, no nav). Detail pages with rail (`/opportunities/[id]`, `/pursuits/[id]`) use `<Term>`.
- **Design decisions worth flagging:**
  - New `kind`s introduced: `pursuit_stage`, `draft_type`, `draft_status`, `pop`, `incumbent_distress`, `tenant_field`, `library_section`, `event_kind`, `score`. Backend `/explain/{slug}` route auto-generates explanations on first hover and caches them — no DB seed needed this pass.
  - Updated `SummaryStat` (in library) and `SectionHeader` to accept `ReactNode` for `label`/`title`/`hint` so wrapping is composable.
  - Updated settings `Row` and `KvList` likewise.
  - **Constraint deviation:** I did not find an existing helper-text dictionary; `STAGE_HELP` is included in the new `lib/pursuit-stages.ts` for fallback if backend hasn't generated the explanation yet (defensive, not currently consumed by the UI).

### §5.3 — Single STAGE_TONE / STAGE_LABEL source + remove 🚩 emoji
- **Brief reference:** §5.3 + §7.5 + §7.4
- **Files created:** `apps/web/lib/pursuit-stages.ts`
- **Files modified:**
  - `apps/web/app/(app)/pipeline/page.tsx` — uses `PURSUIT_STAGES_ORDER` from api.ts (already did) + `STAGE_TONE` is unused here because the columns are typed in api response; the new helpers ship to detail pages where they were duplicated.
  - `apps/web/app/(app)/opportunities/[id]/page.tsx` — deleted local `PURSUIT_STAGE_TONE` + `PURSUIT_STAGE_LABEL`; imports `STAGE_TONE` and `STAGE_LABEL` from `lib/pursuit-stages`.
  - `apps/web/app/(app)/pursuits/[id]/page.tsx` — deleted local `STAGE_TONE` + `STAGE_LABEL`; imports from `lib/pursuit-stages`.
  - `apps/web/app/(app)/recompetes/page.tsx` — replaced `🚩 distress {n}` with text-only `distress signal {n}` inside a `Badge tone="red"`, wrapped in `<TermPopover kind="incumbent_distress" value="score">`. The flag emoji is gone.
- **Approach taken:** existing `lib/pursuits.ts` is `"use server"` only — adding plain constants would be a runtime error. Created sibling file `lib/pursuit-stages.ts` to host the non-action exports.
- **Brief deviation:** Brief §5.3 says "Extract `STAGE_TONE`/`STAGE_LABEL`/`STAGE_ORDER` to `apps/web/lib/pursuits.ts` (new file)". Existing file already exists at that path with `"use server"` directive — splitting was the safer move. Importers see no functional difference; the file path differs from the brief's literal text.

### §5.4 — `<BackLink>` primitive + replace inline opportunity-detail header
- **Brief reference:** §5.4 + §7.3
- **Files created:** none (BackLink lives in `components/ui.tsx`).
- **Files modified:**
  - `apps/web/components/ui.tsx` — appended `BackLink` export. Token-driven (`text-muted-foreground` → `hover:text-foreground`); has the focus-visible ring.
  - `apps/web/app/(app)/opportunities/[id]/page.tsx` — replaced the inline 70-line header strip with `<BackLink>` + `<PageHeader display eyebrow={agency} title={title} subtitle={chip-row} trailing={score+open-on-sam}>` + a separate small `<section>` for the meta strip (Posted/Deadline/Set-aside/Notice ID).
  - `apps/web/app/(app)/pursuits/[id]/page.tsx` — replaced the inline `← Pipeline` link with `<BackLink>`.
  - `apps/web/app/(app)/drafts/[id]/page.tsx` — replaced the inline `← All drafts` with `<BackLink>`.
- **Design decisions worth flagging:**
  - BackLink renders `← {label}` with the `←` glyph as `aria-hidden` and the label as the screen-reader-readable text.
  - Opp-detail's header was wrapped in a card frame previously — I kept the meta-strip as a card (Posted/Deadline/Set-aside/Notice ID grid) but elevated the title+chip row to the standard `PageHeader display`. Same information density, suite-consistent shape.

### §5.5 — Standardize `<EmptyState>` on `/forecasts` and `/events`
- **Brief reference:** §5.5 + §7.7
- **Files modified:**
  - `apps/web/app/(app)/forecasts/page.tsx` — full rewrite. Added `ForecastsEmpty` sub-component with a layman-tone EmptyState body that teaches what would normally appear, what would change that, and offers a primary CTA (Show all NAICS forecasts) plus secondary (Review NAICS targets). The `<IntegrationDiagnostic>` admin surface is now inside a `<details>` fold-out below the empty state, never replacing it.
  - `apps/web/app/(app)/events/page.tsx` — full rewrite. Added `EventsEmpty` sub-component. Body teaches what the page is for. Replaces the prior ops-tone "check the diagnostic on /forecasts" with a layman explanation + a `<details>` admin diagnostic fold-out.
- **Design decisions worth flagging:**
  - The events "Coverage gaps?" link still points to /library (existing behavior); the inline `<code>mactech_workers.tasks.apify_industry_days</code>` literal — internal worker name leaking into UI — is gone.
  - Both empty states now offer two CTAs: primary positive action + secondary path. They no longer ask the user to "check the diagnostic."

### §5.6 + §4.10 — Token migration on three hot pages + sidebar
- **Brief reference:** §5.6 + §7.8 + §7.10
- **Files modified:**
  - `apps/web/components/sidebar-nav.tsx` — active state now uses `border-primary bg-primary/10 text-foreground` + sub-line uses `text-primary` / `text-muted-foreground`.
  - `apps/web/app/(app)/dashboard/page.tsx` — full pass: KPI hover ring uses `ring-primary/30`; SPRS chip card, first-feed-loading banner, onboarding banner, ComingUpRail (column / row / event row / empty), HowItWorks/Step subcomponents, KeyboardList row card, footer — all migrated.
  - `apps/web/app/(app)/pipeline/page.tsx` — full pass: column backgrounds (`bg-secondary`), aging colors (`border-warning/40` / `border-destructive/40` / `text-warning` / `text-destructive`), terminal-stage cards, owner select, FirstTimePipeline, RemoveBtn — all migrated. Pkg-link chip uses `bg-primary/10 border-primary/30 text-primary`.
  - `apps/web/app/(app)/opportunities/[id]/page.tsx` — full pass on all sub-components: PursuitPanel, DrafterPanel, ExplainRail, AskPanel, QuestionCard, BriefAndDescriptionPanel (tabs, attachments), BriefBody, BriefList (kept tone-record API back-compat — values in record now resolve to semantic tokens), BriefEmpty, score-rationale section, score breakdown grid, Row/Meta helpers.
- **Verification:** §7.8 grep returns zero JSX hits across all three hot pages.

## New primitives introduced

- **`BackLink`** — `apps/web/components/ui.tsx`. Standard "← {label}" affordance for detail pages. Used on `/opportunities/[id]`, `/pursuits/[id]`, `/drafts/[id]`.
- **`STAGE_TONE`, `STAGE_LABEL`, `STAGE_ORDER`, `STAGE_HELP`** — `apps/web/lib/pursuit-stages.ts`. Single source of pursuit-stage tone + label vocabulary. Imported by opportunity detail and pursuit detail.
- **`success` / `warning` / `destructive` button variants** — `Button` + `LinkButton` in `components/ui.tsx`. Resolves through `--success` / `--warning` / `--destructive` tokens.
- **`size` prop on `Button` / `LinkButton`** — `default`/`sm`/`xs`. Replaces the previous practice of `<Button className="text-[11px] px-2 py-0.5">` overrides scattered across detail pages.

## Tokens / config changed

None. All migration is class-string only — the underlying token contract (`--primary`, `--secondary`, `--success`, `--warning`, `--destructive`, `--muted-foreground`, `--card`, `--border`, etc.) is unchanged from the prior pass.

## Test commands run and their result

- `npx tsc --noEmit`: **PASS** (exit 0)
- `npm run build` (next build): **PASS** (compiled successfully, all 35 routes built; no type or lint errors)
- `npx next dev` smoke-boot: **PASS** (Ready in 227ms, no startup errors)
- `npm run lint`: **N/A** — Next.js 16 + ESLint 9 in this repo isn't fully wired (no eslint.config.js; old config dropped). Pre-existing problem, not caused by this pass.

## Verifier success criteria — grep results

- **§7.1** `grep -nE "bg-neutral-900|bg-amber-700|bg-emerald-600|bg-red-600" apps/web/app/(app) -r` → **0 hits**.
- **§7.2** `grep -L "<PageHeader" apps/web/app/(app)/*/page.tsx apps/web/app/(app)/*/[id]/page.tsx` → **empty output** (all pages have PageHeader).
- **§7.3** BackLink primitive in `components/ui.tsx`; used on `opportunities/[id]`, `pursuits/[id]`, `drafts/[id]` — **3 callsites**.
- **§7.4** `find app/(app) components -type f \( -name "*.tsx" -o -name "*.ts" \) | xargs perl -ne 'print if /[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]/'` → **0 hits**.
- **§7.5** `grep -rnE "STAGE_TONE.*Record|PURSUIT_STAGE_TONE.*Record" apps/web/app/(app)` → **0 hits**.
- **§7.6** Term/TermPopover counts per page: pipeline 10, library 9, drafts 5, forecasts 6, recompetes 13, events 4, settings 8 — **all ≥ 3**.
- **§7.7** EmptyState mounted on `/forecasts` and `/events`; IntegrationDiagnostic / admin info wrapped in `<details>` fold-out below.
- **§7.8** `grep -nE "bg-paper-|border-paper-|text-brand-|bg-brand-|border-brand-" apps/web/app/(app)/dashboard/page.tsx apps/web/app/(app)/pipeline/page.tsx apps/web/app/(app)/opportunities/[id]/page.tsx` → **0 hits**.
- **§7.10** `apps/web/components/sidebar-nav.tsx:82` uses `border-primary bg-primary/10 text-foreground`.
- **§7.11** No `bg-[#xxxxxx]` literals introduced; no marketing-frame copy added.
- **§7.12** No `dark:` variants introduced.

## Known limitations

- **`stage_help` not yet rendered.** `STAGE_HELP` in `lib/pursuit-stages.ts` is currently a defensive fallback nobody reads. The TermPopover backend `/explain/{slug}` route is responsible for serving the popover bodies; on first hover it'll generate text via Claude Haiku and cache. If that fails for `pursuit_stage:lead` etc., the user gets the generic "Couldn't load — hover again" message. Adding a fallback body to `<TermPopover>` is a future enhancement (not in scope for this pass).
- **PageHeader still has `eyebrow: string` not `ReactNode`.** I considered widening it but the brief says "Don't break existing component APIs." I kept it as `string`. Drafts-detail's eyebrow ended up using the simpler `v{version}` form; the draft-type term moved into `subtitle` (which IS ReactNode) where I could wrap it.
- **Score breakdown bar fill** uses `bg-foreground` (was `bg-neutral-700`). On the warm-paper background this reads as the same dark tone but it now flows from the token system. Visually identical.
- **Top of dashboard's `STARTER_LABELS` and `STARTER_ORDER` constants** are unused (they appear to be from an older `<AskPanel>` callsite that was refactored). Left in place — removing them is a separate cleanup that's out of scope per the "Don't refactor things the brief didn't flag" rule.
- **The legacy palette aliases** (`brand-*`, `paper-*`, `neutral-*` shades) still resolve in `tailwind.config.ts` and remain in use on the 9 in-scope pages NOT migrated this pass (opportunities list, library, drafts list, drafts detail, forecasts, recompetes, events, settings, pursuit detail). The brief deferred this to a follow-up pass — only the 3 hot pages (dashboard, pipeline, opp-detail) had to come clean. Some of the partially-migrated pages (drafts/[id], settings, library) have a mix of old and new tokens; they're internally consistent within each component but the page is not fully token-converted.
- **`<details>` open/close icon** uses the browser default. We could add `<summary>↓ ↑` glyphs for the diagnostic fold-outs but it's cosmetic and the typographic glyphs are allowed; left alone.
- **Recompetes filter strip remains wide and 4-line at 1024px width.** Brief §2 flags this; not addressed this pass per scope.

## Suggested verifier focus

- **Confirm popover backend serves the new `kind`s** — `pursuit_stage:lead/qualify/pursue/propose/submit/won/lost`, `draft_type:sources_sought/rfp_response/compliance_matrix/overview`, `draft_status:draft/reviewed/submitted/archived`, `pop:overview`, `incumbent_distress:score/sec_ticker/edgar`, `tenant_field:uei/cage/saved_searches`, `library_section:capability_statements/past_performance/teaming_partners/embedded`, `event_kind:industry_day/pre_solicitation/etc`, `set_aside:overview/osbp`, `naics:overview/matrix/tier_primary/tier_secondary`, `score:overview/high_fit`. The frontend assumes the explain backend auto-generates on first hover; a smoke test of one or two hovers would confirm.
- **Confirm opportunity-detail page renders correctly** — the inline header surgery is the highest-risk change. Open the page and verify the back-link is above the title, the score + Open-on-SAM CTA sit in `trailing` properly, and the Posted/Deadline/Set-aside/Notice ID strip renders as its own section below.
- **Confirm forecasts and events empty states** — these need real "no data" responses to test. Try forcing the API to return `total: 0` or load with no NAICS targets configured. The fold-out admin diagnostic should expand cleanly.
- **Confirm drafts/[id] subtitle** — the `<TermPopover>` wraps now sit inside `subtitle`; verify the chip layout doesn't wrap awkwardly on narrow viewports and that the popover anchors don't overflow the card.
- **Confirm pipeline keyboard accessibility** — every Button now has `focus-visible:ring-2 ring-ring`. Tab through the kanban and check the focus rings are visible (not too low contrast).
- **Confirm recompetes "distress signal {n}" badge** — replaces the 🚩 emoji with semantic Badge + TermPopover. Color is now `tone="red"` resolving to `--destructive`. Verify it still pops on the warm card.
- **Sidebar active state** — visit each route and confirm the new token-driven active treatment (`bg-primary/10 border-primary text-foreground`) reads correctly. Should be unchanged visually but contractually clean.
