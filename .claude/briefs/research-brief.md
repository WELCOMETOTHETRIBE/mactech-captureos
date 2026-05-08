# UX Research Brief — CaptureOS "Gold Copy" Port from `vetted` (clearD)

Generated: 2026-05-08T12:52:40-07:00
Scope: `apps/web/` (Next.js 14 App Router) — every authenticated surface (`app/(app)/**`), the marketing landing (`app/page.tsx`), the auth shells (`app/sign-in`, `app/sign-up`), and shared primitives (`components/`). Reference repo: `WELCOMETOTHETRIBE/vetted` (the clearD product).

## 1. Product summary

MacTech CaptureOS is a multi-tenant federal-capture/BD platform — opportunity scoring, pipeline kanban, capture packages, and a proposal drafter — built first as MacTech's internal capture weapon (4 named founders, four pillars: Quality / Security / Infrastructure / Governance). Phase 1 users are the founders themselves; Phase 4 is external SaaS. The frontend is a deliberate inversion of the typical "dark cybersecurity" cliché: warm-paper backgrounds, brand teal `#207b78`, hairline borders, optional italic-serif page titles — a "serious documents, not dashboards" feel that MacTech built on purpose (commit `6734e93 ux(sprint-a): warm-paper neutrals + hairline borders + italic-serif page titles`).

`vetted` is a sister MacTech product — clearD, a clearance-first professional networking site (LinkedIn-for-cleared-talent). It uses a full shadcn/ui CSS-variable contract, `dark`-by-default with an "obsidian + copper" palette (warm charcoal `24 6% 7%` background, burnished copper `#F1994C` primary), and semantic tokens (`--success`, `--warning`, `card`, `popover`, `accent`). Both apps share a `MacTechFooter` component already.

## 2. Stack & design system inventory

### CaptureOS (current)
- **Framework:** Next.js 16.2 (App Router), React 18, TypeScript 5.6
- **UI library:** None — custom primitives in `apps/web/components/ui.tsx` (`Card`, `Section`, `PageHeader`, `Kpi`, `Badge`, `ScoreBadge`, `Button`, `LinkButton`, `EmptyState`, `Pillar`, `NaicsBadge`, `SetAsideBadge`, `NoticeTypeBadge`, `Term`, `ExplainLink`)
- **Styling:** Tailwind 3.4 (classic config, not v4). No `cn()` util, no `class-variance-authority`, no Radix
- **Auth:** Clerk 6.18
- **Existing primitives:** ~25 page-specific components in `apps/web/components/` (e.g. `agency-intel-card`, `cyber-posture-card`, `term-popover`, `cmd-k`, `solicitation-panel`)
- **Existing design tokens** (`apps/web/tailwind.config.ts`):
  - `brand.50–950` teal scale (`#207b78` = brand-600, anchor color)
  - `paper.50–900` warm-neutrals scale (`#faf9f5`, `#f3f1ea`, `#e9e5d9`, etc.)
  - `font-sans`: system fonts only (no Google Fonts)
  - `font-serif`: Iowan Old Style → Palatino → Hoefler → Georgia (used for opportunity/pursuit page titles when `display={true}`)
  - Default `ring` color set to `#207b78`
  - `globals.css` (`apps/web/app/globals.css:1-48`): bumps base `body` to 15px / line-height 1.55; `:focus-visible` ring; Clerk autofill polish
- **Light-mode only** — there is no `dark:` variant strategy in the codebase.

### vetted / clearD (reference)
- **Framework:** Next.js 14, React, TypeScript
- **UI library:** Full shadcn/ui (`components/ui/`: 25 primitives — accordion, alert, badge, button, card, checkbox, dialog, dropdown-menu, input, label, select, sheet, skeleton, switch, table, tabs, textarea, toast, tooltip, plus `ConfirmDialog`, `Drawer`, `Notice`)
- **Styling:** Tailwind v4 (`@import "tailwindcss"`, `@theme inline {...}` in CSS), CSS variables driving everything via `hsl(var(--*))` contract
- **Auth:** Clerk
- **Tokens (vetted's `app/globals.css`):**
  - HSL CSS-vars for: `background`, `foreground`, `card`, `popover`, `primary`, `secondary`, `muted`, `accent`, `destructive`, `success`, `warning`, `border`, `input`, `ring`
  - Dark mode: `--background: 24 6% 7%` (warm charcoal), `--primary: 28 85% 62%` (burnished copper / `#F1994C`), `--accent: 28 50% 18%` (deep ember)
  - Light mode kept "for completeness — clearD is dark-first"
  - `--radius: 0.5rem`, plus radius-sm/md derivations
  - `--font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Inter, sans-serif`
  - `--font-mono: ui-monospace, SFMono-Regular, Menlo, monospace` (no monospace token in CaptureOS today)
- **Signature visual utilities** (vetted-only):
  - `.brand-mark-chip` — burnished-copper inset chip (used as logo/pillar mark)
  - `.grid-bg` — 32px subtle grid overlay
  - `.cleard-hero-bg` — radial-gradient hero (primary glow top-left, accent glow bottom-right)
  - `.glass`, `.glass-elevated` — card/0.92 alpha + 12px backdrop-blur
  - `.card-modern`, `.btn-modern`, `.text-balance`, `.animate-on-scroll`
  - `.container-fluid` — 1400px max-width container
- **Layout primitives:** `components/layout/cleard-shell.tsx`, `cleard-sidebar.tsx`, `cleard-topbar.tsx`, `mactech-footer.tsx`, `page-header.tsx`. Vetted's shell is `flex min-h-screen` with a 64-unit fixed sidebar + sticky 14-unit topbar; main is `bg-background text-foreground p-4 md:p-8`.

## 3. Activity signals (last 60 days)

- **Hot files (top 10 in `apps/web/`):**
  1. `apps/web/lib/api.ts` (25 commits)
  2. `apps/web/app/(app)/dashboard/page.tsx` (19)
  3. `apps/web/app/(app)/opportunities/[id]/page.tsx` (18)
  4. `apps/web/app/sign-up/[[...sign-up]]/page.tsx` (11)
  5. `apps/web/app/sign-in/[[...sign-in]]/page.tsx` (11)
  6. `apps/web/components/ui.tsx` (7)
  7. `apps/web/components/sidebar-nav.tsx` (7)
  8. `apps/web/app/globals.css` (7)
  9. `apps/web/app/(app)/pipeline/page.tsx` (6)
  10. `apps/web/app/(app)/layout.tsx` (6)
- **Active surface areas:** Dashboard greeting + KPIs + ComingUpRail; opportunity detail w/ jargon popovers + ExplainRail; auth pages have been polished four times. Pursuit detail and capture package surfaced last sprint.
- **Recent design intent (commit log):** `6734e93 ux(sprint-a): warm-paper neutrals + hairline borders + italic-serif page titles` introduced today's brand. `1291fd0 ux(auth): unified MacTech dark sign-in design (mirrors QMS) — teal accent for capture` says the auth page was *deliberately* aligned to the QMS app's dark style — so the cross-suite design conversation is already happening and authenticated app + auth pages currently use **two different palettes**.
- **Team size signal:** Active development is concentrated; recent commits suggest 1–2 hands on the frontend, with `apps/web` evolving in tight, intentional sprints. This means a token migration is feasible in 1–2 sittings — there is no "team-wide stop-the-world" cost.

## 4. User-reported pain points

GitHub MCP is not connected in this session, so I cannot pull live issues/PRs. I did not invent any. **Recommendation: connect the GitHub MCP and re-run a slim pass** focused on issues tagged `ux`, `design`, or labels mentioning `tokens`/`branding` before the architect ships.

What I can read from the code as quasi-evidence:
- The auth pages encode brand color as **string-interpolated arbitrary Tailwind hexes** (e.g. `bg-[${BUTTON}]`, `border-[${ACCENT}]`) — this is a code smell that suggests the team had no token contract to lean on. **Evidence strength: high (in-source).**
- 56 occurrences of arbitrary hex (`#xxxxxx`) classes in `apps/web/app` + `apps/web/components`. Most concentrate in the two auth pages and `footer.tsx` (`bg-[#0A0A0A]`, `border-[#1f1f1f]`, etc.). **Evidence: high.**
- The dashboard greeting was tightened twice in the last week (`e44699c` and earlier sprint-c reshuffles) — multiple iterations on the same surface signals continuing dissatisfaction with hierarchy/density at the top of the dashboard. **Evidence: medium (inferred from commit pattern).**
- `Pillar` component renders pillars as hardcoded color tones (`security: blue, infrastructure: green, quality: amber, governance: violet`). These mappings are duplicated implicitly in the dashboard's amber/red/brand `Kpi` tones. There is no semantic mapping in tokens. **Evidence: high.**

There is **no `Feedback` model in the schema** that I can see referenced from the frontend (`apps/web/lib/api.ts` has no `feedback` calls and the docs list points to `SCHEMA.md`, which I did not read in full). If a UX-feedback surface exists in the API, the architect should query it before locking the leverage points.

## 5. Inferred user & critical path

- **Primary user persona (Phase 1, evidence-backed):** The four named founders. CLAUDE.md §1 lists them by name, role, pillar. They are senior practitioners but **not all read code fluently** ("Brian and John are less code-oriented" — CLAUDE.md §8). Density and jargon are real risks; that is why the dashboard was de-densified in sprint-c (`d638ab1`) and why the `Term`/`TermPopover`/`ExplainRail` machinery exists (`5b36d7b`).
- **Top 3 jobs-to-be-done (from `app/(app)/` + dashboard layout):**
  1. *Triage today.* Open the app → see "what should I do today" → click into 1–3 high-fit opps. (Implemented: `TodaysMoves`, KPI tiles, "Your top N" list.)
  2. *Manage active pursuits.* Track lead → submit → won/lost on `/pipeline`. (Kanban + per-pursuit detail.)
  3. *Stay eligible.* Glance the SPRS chip, the eligibility blockers card, and finish onboarding. (Tenant-eligibility card, SPRS section.)
- **Critical path (login → core action):**
  1. `/sign-in` (dark Clerk shell, two-column hero) →
  2. `/dashboard` (greeting + KPIs + TodaysMoves + your top + ComingUpRail) →
  3. `/opportunities/[id]` (triage view with score, why-it-matters, jargon popovers) →
  4. "Add to pipeline" → `/pursuits/[id]` (deep-work home) →
  5. `/drafts/[id]` (Sources Sought / RFP draft generation).
- **Friction points observed in code:**
  - The auth pages use a fully-different visual language (dark obsidian, big radial glows, `bg-gradient-to-br from-[#04060a]`) vs. the authenticated app (warm-paper, hairline). **Sign-in promises one product; the dashboard delivers another.** This is the single biggest brand inconsistency.
  - `apps/web/components/footer.tsx` is hardcoded dark (`bg-[#0A0A0A]`) and is mounted **at the bottom of the warm-paper authenticated app shell** (`apps/web/app/(app)/layout.tsx:103`). On the dashboard you scroll through warm-paper white cards then hit a slab of obsidian. That's a brand jolt.
  - 143 `bg-paper-/bg-brand-/text-brand-/border-paper-` hits is healthy adoption; the contradiction is the 56 arbitrary-hex hits clustered in auth + footer that bypass the tokens.
  - No semantic tokens — `tone="amber"` in `Kpi` and `Badge` means "amber the visual color," not "warning the meaning." Porting to vetted's `--warning` / `--success` / `--destructive` / `--accent` would let the same component carry meaning across themes.
  - Visible opportunity: `card-modern`, `glass`, `grid-bg`, `cleard-hero-bg` from vetted are exactly the kind of signature utilities that would give CaptureOS recognizable brand "tells" without invading copy or violating the sober-voice constraint.

## 6. Recommended aesthetic direction

- **Direction:** **Editorial / B2G credibility** in the authenticated product (current CaptureOS direction is correct), **with the vetted shadcn-token contract underneath as the cross-suite design system**, and **with the auth/marketing surfaces converted from "obsidian + copper" cyber-style to "warm-paper editorial" so the entire app reads as one product**. In short: keep CaptureOS's warm-paper-and-teal palette, adopt vetted's *token architecture* (CSS-vars, semantic names, `--radius`, `cn()` utility, shadcn primitives), and unify the auth shell to the same warm direction.
- **Rationale:**
  1. CaptureOS users are CO/KO/CISO/BD-lead types (CLAUDE.md §3). They expect documents, not consoles. The warm-paper direction — explicitly chosen in `6734e93` — already works.
  2. clearD is a *consumer-ish networking* product where dark obsidian + copper reads as "premium professional." CaptureOS is an *enterprise capture/compliance* product. **Porting clearD's color palette wholesale would violate the existing brand decision.** What we want is the *system*, not the *skin*.
  3. The current contradiction (warm app, dark auth, dark footer) is the real problem. Resolving it toward the warm direction makes every surface coherent.
  4. The shadcn-via-CSS-vars contract is reusable: same components, swap variables, every MacTech app gets a different but related skin. clearD = obsidian/copper. CaptureOS = paper/teal. GovernanceOS / ProposalOS / Quality / Codex inherit later.
- **Visual language specifics:**
  - **Color foundation** (preserve, but re-express as HSL CSS vars):
    - `--background: 45 35% 97%` (paper-50 `#faf9f5`)
    - `--foreground: 24 6% 12%` (near-black; tightens current `#1f1f1f`)
    - `--card: 0 0% 100%` (white)
    - `--primary: 178 58% 30%` (brand-600 `#207b78`)
    - `--primary-foreground: 0 0% 100%`
    - `--secondary: 45 25% 93%` (paper-100)
    - `--muted: 45 25% 93%`
    - `--muted-foreground: 24 6% 38%`
    - `--accent: 178 30% 90%` (a soft brand-tinted accent)
    - `--border: 45 18% 88%` (paper-200)
    - `--ring: 178 58% 30%` (matches primary)
    - **Semantic** (replaces ad-hoc tone="amber"/"red"/"green"): `--success: 145 55% 32%`, `--warning: 32 90% 38%`, `--destructive: 0 70% 45%`, plus pillar tokens `--pillar-security` / `--pillar-infrastructure` / `--pillar-quality` / `--pillar-governance` so `Pillar` chip styling stops being string-keyed.
  - **Typography character:** keep system-sans for body, keep the editorial `font-serif` stack for opportunity/pursuit/capture-package headers (when `display={true}`). Add a `--font-mono` token for tabular score/dollar/date columns (already used as `tabular-nums`; mono token formalizes it).
  - **Density:** hairline borders (`border-paper-200`), `text-sm`/15px floor, `p-5/p-6` cards, `space-y-8` page rhythm — keep current.
  - **Motion posture:** subdued. Adopt vetted's `.animate-on-scroll` (600ms cubic-bezier) for first-paint section reveals only. **Reject** vetted's hero radial-glow auras and grid-bg in the dashboard — they read "marketing site" and CaptureOS isn't selling to itself.
- **What to AVOID for this product:**
  - Wholesale dark mode default. CaptureOS is light-first.
  - Copper `#F1994C` as primary. The teal is the brand decision.
  - Glass / backdrop-blur on dashboard cards (the `.glass` utility). Keep cards opaque; reserve glass for popovers/dialogs only.
  - Big radial-gradient hero auras on authenticated surfaces.
  - Vetted's `text-balance` on body paragraphs (it's a hero/h1 utility; using it in body kills predictable wrapping at responsive breaks).
  - `.brand-mark-chip` styled as a chunky badge mark — CaptureOS's existing eyebrow + serif title is more appropriate to the audience.

## 7. Top UX leverage points (ranked by impact / effort)

1. **Adopt vetted's CSS-variable token contract, translated to CaptureOS palette.**
   - Problem: Tokens live in `tailwind.config.ts` as static hex; auth pages reach around them with `bg-[${ACCENT}]` template-string hacks; no `dark:`/theme primitive; no semantic `--success/--warning/--destructive`.
   - Evidence: 56 arbitrary-hex usages, mostly in `apps/web/app/sign-in/[[...sign-in]]/page.tsx` and `app/sign-up/[[...sign-up]]/page.tsx` and `components/footer.tsx`. Vetted's `app/globals.css` shows the target contract.
   - Proposed direction: Replace `apps/web/app/globals.css` token block with HSL-var contract (light-first, vars listed in §6). Update `tailwind.config.ts` to map `bg-background / bg-card / bg-primary / text-muted-foreground / etc.` to those vars. Keep `paper.*` and `brand.*` scales as legacy aliases for the migration window.
   - Impact: **High** — unblocks every other leverage point, kills 56 hex hacks in one swing, gives the architect a typed surface.
   - Effort: **M** (one PR, maybe a half day; mostly mechanical).
   - Files: `apps/web/app/globals.css`, `apps/web/tailwind.config.ts`.

2. **Unify the auth pages to the warm-paper direction (kill the obsidian-copper sign-in).**
   - Problem: `app/sign-in` and `app/sign-up` are full-bleed dark `bg-[#0A0A0A]` two-column hero with cyan/teal glass cues and inline hex variables — they do not match the warm-paper authenticated app the user sees one click later.
   - Evidence: `apps/web/app/sign-in/[[...sign-in]]/page.tsx:92` (`bg-[#0A0A0A] text-gray-100`), `apps/web/app/(app)/layout.tsx:19` (`bg-paper-50`). Same `bg-[${BUTTON}]` template hack repeated 11 commits in a row trying to polish this surface.
   - Proposed direction: Re-skin auth as a single column on warm-paper-50 with white card, brand-teal primary button, system-sans, the existing 3-trust-cue list demoted to a sober paper-100 sidebar (or removed on Phase 1 since real users are 4 known founders). Re-derive Clerk `appearance` from the new tokens, not from inline hex.
   - Impact: **High** — single biggest visual incoherence in the product. Every login is a brand jolt today.
   - Effort: **M** (1 day for both pages, including Clerk `appearance` map).
   - Files: `apps/web/app/sign-in/[[...sign-in]]/page.tsx`, `apps/web/app/sign-up/[[...sign-up]]/page.tsx`.

3. **Re-skin `MacTechFooter` to a warm-paper variant (kept dark in vetted; should be paper here).**
   - Problem: The shared `MacTechFooter` (`components/footer.tsx`) is hardcoded `bg-[#0A0A0A]`. It anchors the bottom of every authenticated page in the warm-paper app and clearly belonged to a different palette decision.
   - Evidence: `components/footer.tsx:19` and `app/(app)/layout.tsx:103` (footer mounted inside the warm shell).
   - Proposed direction: Take a CaptureOS variant of the footer that uses `bg-paper-100 border-paper-200 text-neutral-500` and brand-teal hovers. Keep the same `APPS`/`COMPANY` link content so the cross-suite hop still works. Vetted can keep its dark variant — they already share component code only conceptually, not via package import.
   - Impact: **High visual / Low risk** — the user feels it instantly on every page.
   - Effort: **S** (~1 hour).
   - Files: `apps/web/components/footer.tsx`.

4. **Introduce shadcn-style primitives + `cn()` util as the upgrade path for `components/ui.tsx`.**
   - Problem: `components/ui.tsx` is a single 589-line file mixing primitives (Card, Button, Badge) with domain components (ScoreBadge, NoticeTypeBadge, SetAsideBadge, Pillar) and formatters (fmtMoney, fmtDate, fmtRelativeDays). No `cn()`, no `cva`, no `forwardRef`, no Radix.
   - Evidence: `apps/web/components/ui.tsx:1-589`. Vetted's `components/ui/button.tsx` shows the target shape.
   - Proposed direction: Add `lib/utils.ts` with `cn()`, install `class-variance-authority` and `@radix-ui/react-slot`, and split `ui.tsx` into `components/ui/{button,badge,card,kpi,empty-state,page-header}.tsx` matching vetted's filenames. Keep domain primitives (`ScoreBadge`, `Pillar`, `NaicsBadge`, `SetAsideBadge`, `NoticeTypeBadge`) in `components/domain/` so the shape of `components/ui/` stays portable across MacTech apps. **Migrate, don't rewrite** — only the surfaces touched by this sprint need to switch.
   - Impact: **High** (long-term: every future component lands shadcn-shaped; cross-app reuse becomes possible).
   - Effort: **M** for the scaffolding + Card/Button/Badge migration; **L** if you migrate every primitive in one pass.
   - Files: new `apps/web/lib/utils.ts`, new `apps/web/components/ui/` directory, refactored `apps/web/components/ui.tsx` (or split-and-delete).

5. **Replace `app/(app)/layout.tsx` with a `MacTechShell` — sidebar + topbar + main, matching vetted's shape.**
   - Problem: The current `(app)/layout.tsx` is 114 lines of hand-laid grid + ad-hoc sidebar wrapper + bespoke header. Vetted has the same structure factored into `cleard-shell.tsx` + `cleard-sidebar.tsx` + `cleard-topbar.tsx` + `page-header.tsx`. Sharing the shell *shape* (not the colors) makes future MacTech apps trivially scaffold-able.
   - Evidence: `apps/web/app/(app)/layout.tsx:18-114`; vetted `components/layout/cleard-shell.tsx`.
   - Proposed direction: Extract `apps/web/components/layout/{capture-shell,capture-sidebar,capture-topbar,page-header}.tsx`. `PageHeader` already exists in `components/ui.tsx` — pull it into `layout/page-header.tsx` so the shape matches vetted.
   - Impact: **Medium** (mostly architectural cleanliness; user sees a slightly tighter shell).
   - Effort: **M**.
   - Files: new `apps/web/components/layout/*`, refactor `apps/web/app/(app)/layout.tsx`.

6. **Redo the marketing landing (`app/page.tsx`) as a 60-line warm-paper hero, then stop.**
   - Problem: `app/page.tsx` is a 39-line stub: `text-3xl font-semibold` title, two buttons, footer. It's fine for Phase 1 (auth-gated, real users sign in directly) but it's the only public surface and it's drab.
   - Evidence: `apps/web/app/page.tsx:9-38`. CLAUDE.md §2 says "Phase 4+ is external SaaS — don't recommend marketing-site work that would only matter at Phase 4," so this is bounded.
   - Proposed direction: Use the new tokens. Add a brand-teal eyebrow, italic-serif `display` title (matches dashboard treatment when used on pursuits/opps), a 1-line pitch, "Sign in" as primary teal button, "Sign up" ghost button. **Do not** port vetted's audience-cards / systems-cards grid — that's marketing surface area, out of Phase 1 scope.
   - Impact: **Low** (4 founders log in, not browse).
   - Effort: **S** (~30 min).
   - Files: `apps/web/app/page.tsx`.

7. **Add semantic tone tokens (`--success`, `--warning`, `--destructive`) and migrate `Kpi` / `Badge` / `Pillar` to use them.**
   - Problem: `Kpi tone="amber"` and `Badge tone="amber"` directly encode color, not meaning. There is no path to (eventually) themable severity.
   - Evidence: `apps/web/components/ui.tsx:139-145, 169-177`. Vetted's `components/ui/badge.tsx` ships `default`, `success`, `warning`, `destructive`, `outline`, `muted` variants by meaning.
   - Proposed direction: Keep the current `tone` prop API (don't break callers) but resolve `amber` → `warning`, `red` → `destructive`, `green` → `success`, `brand` → `primary` via the new HSL vars. This is mostly a `globals.css` patch and a `Kpi`/`Badge` `valueTones`/`tones` map rewrite — calling code stays identical.
   - Impact: **Medium**.
   - Effort: **S**.
   - Files: `apps/web/components/ui.tsx` (specifically the `valueTones` and `tones` records), `apps/web/app/globals.css`.

8. **Promote the `Term`/`TermPopover`/`ExplainRail` jargon-helper system to a documented brand pattern.**
   - Problem: This is one of CaptureOS's strongest brand differentiators (Brian and John can read jargon-dense pages because every CMMC/SPRS/FAR/Section-L term has an inline ? affordance). It has no name, no system doc, and isn't listed alongside the design tokens — so it'll be inconsistent across new pages.
   - Evidence: `components/term-popover.tsx`, `components/ui.tsx:374-394` (`Term` component), commits `5b36d7b feat(ui): popover Term + auto-anchored prose` and `2ba0ecc feat(ui): inline jargon helpers`. Vetted has no equivalent.
   - Proposed direction: Codify "any jargon term in a page surface MUST be wrapped in `<Term kind=... value=... />`" as a documented brand rule. Add a brief style guide note in `apps/web/components/ui/README.md` (or `docs/DESIGN_SYSTEM.md`) listing the supported `kind`s. This isn't styling — it's the brand voice in code.
   - Impact: **Medium** (ensures the most-loved feature stays consistent as new pages land).
   - Effort: **S** (15 min, doc-only).
   - Files: new `docs/DESIGN_SYSTEM.md` or `apps/web/components/README.md`.

9. **Standardize `--radius`, `--font-mono`, and a `tabular-nums` rule for money/score/date columns.**
   - Problem: Radii are ad-hoc (`rounded-md`, `rounded-lg`, `rounded-sm`, `rounded-md` again). Score chips are `tabular-nums` in some places, default in others. There's no `--font-mono` token even though monospace would help dollar/date alignment.
   - Evidence: Mixed `rounded-*` in `dashboard/page.tsx` (lines 270, 277, 387, 542, 656). `tabular-nums` in `Kpi`, `ScoreBadge`, `ComingUpForecastRow`, but not on the `/recompetes` or `/forecasts` lists.
   - Proposed direction: Set `--radius: 0.5rem` like vetted. Add `--font-mono` token. Make `tabular-nums` the default on every `Kpi.value`, every score, every dollar, every date.
   - Impact: **Low / cumulative quality**.
   - Effort: **S**.
   - Files: `apps/web/app/globals.css`, `apps/web/components/ui.tsx`.

10. **Optional: port one signature utility from vetted — `.card-modern` only.**
    - Problem: CaptureOS cards are flat (`border-paper-200 bg-white`, no shadow). They read as "plain" rather than "considered." Vetted's `.card-modern` adds a `box-shadow: 0 1px 2px hsl(0 0% 0% / 0.4)` — too dark for our warm-paper world, but a `0 1px 2px hsl(0 0% 0% / 0.04)` lift would add the smallest hint of paper-on-paper.
    - Evidence: `Card` in `apps/web/components/ui.tsx:24-27` vs vetted `globals.css` `.card-modern`.
    - Proposed direction: Adjusted `.card-modern` utility in `globals.css` with light-mode shadow value; opt-in via `<Card variant="lift">` rather than blanket apply.
    - Impact: **Low** (taste-level polish).
    - Effort: **S**.
    - Files: `apps/web/app/globals.css`, `apps/web/components/ui.tsx`.

## 8. Out of scope / explicit non-goals

- **Don't port vetted's marketing landing.** clearD is selling itself; Phase 1 CaptureOS isn't (CLAUDE.md §2).
- **Don't port vetted's `Feed`/`Profile`/`Jobs`/`Candidates`/`Groups` page templates.** Those are clearD's product surface area, not ours; CaptureOS has `Dashboard`, `Opportunities`, `Pipeline`, `Library`, `Drafts`, `Forecasts`, `Recompetes`, `Events`, `Settings`. Different product.
- **Don't introduce dark mode.** Light-first is the existing brand decision (`6734e93` and the explicit warm-paper choice).
- **Don't kill the editorial `font-serif`.** It's used on opportunity / pursuit / capture-package titles when `display={true}` and is brand DNA. Vetted has no serif story; that's a CaptureOS strength to preserve.
- **Don't refactor `components/agency-intel-card`, `cyber-posture-card`, `solicitation-panel`, `audit-trail-card`, `ask-streaming`, `draft-streaming`** in this pass. They are domain components touched in active sprints (Tier-1 sprint commits in the last 30 days). A token migration that's transparent to them is fine; rewriting their layouts is not.
- **Don't move the `Term`/`ExplainRail` system into shadcn.** It's a CaptureOS-specific affordance and lives correctly outside the generic primitives folder.
- **No emoji in product UI.** Voice rule from CLAUDE.md §3. Vetted's README ends with "Built with ❤️" — that's repo-level chrome, not product UI; do not import any heart/sparkle/checkmark-emoji-as-decoration patterns.

## 9. Branding bits to REJECT from vetted

These are explicit "do not let this make it through":

- **"Built with ❤️"** marketing-tone copy at the bottom of the README and similar tone anywhere in the product. Voice violation.
- **Hero radial-gradient auras** (`.cleard-hero-bg`, the big blurred glows in the auth split-screen). Read as "B2C SaaS landing"; CaptureOS is sober document software.
- **`text-balance` on body copy.** Vetted uses it widely; only safe on h1/h2.
- **"Mission-ready by design" / "audience" / "audiences"** marketing-frame phrasing from clearD's landing. CaptureOS speaks in "founders," "tenants," "pursuits," "opportunities" — direct.
- **Pulsing/animated chips on KPIs** (vetted has nothing of the sort but watch out for it appearing in any "premium" port). Status colors carry the meaning; motion is not needed.
- **Burnished-copper `#F1994C` as primary anywhere**. Brand teal `#207b78` is the decision.
- **Decorative iconography on dashboard cards** (lucide icons in branded chip containers — vetted does this on its audiences/systems cards). CaptureOS uses tabular numbers and small badges; introducing icon-led cards on the dashboard would trade signal for decoration.
- **Hidden Clerk header (`header: "hidden"`) plus a separately rendered title in the page**. Vetted does this; we already do this; mention only because the new auth re-skin should retain the cleaner *visible-Clerk-header* approach if Clerk's defaults render acceptably with our new tokens — fewer string-template `bg-[${ACCENT}]` overrides.

## 10. Success criteria for the verifier

The architect's PR for this iteration succeeds if all of the following are true:

1. `apps/web/app/globals.css` defines `--background`, `--foreground`, `--card`, `--primary`, `--primary-foreground`, `--secondary`, `--muted`, `--muted-foreground`, `--accent`, `--accent-foreground`, `--border`, `--ring`, `--success`, `--warning`, `--destructive`, `--radius`, `--font-sans`, `--font-mono` as HSL CSS variables, in light-mode-first form.
2. `apps/web/tailwind.config.ts` exposes those tokens as Tailwind utilities (`bg-background`, `text-muted-foreground`, `border-border`, `bg-primary text-primary-foreground`, etc.).
3. **Zero arbitrary hex classes** (`bg-[#xxxxxx]`, `text-[#xxxxxx]`, `border-[#xxxxxx]`, `bg-[${VAR}]`) in `apps/web/app/sign-in/`, `apps/web/app/sign-up/`, `apps/web/components/footer.tsx`, `apps/web/app/page.tsx`, `apps/web/app/(app)/layout.tsx`, `apps/web/app/(app)/dashboard/page.tsx`. (`grep -rE "bg-\[#|text-\[#|border-\[#" apps/web/app apps/web/components` returns 0 hits in the listed files.)
4. The sign-in and sign-up pages render on a warm-paper-50 background (no `bg-[#0A0A0A]`, no `bg-gradient-to-br from-[#04060a]`).
5. `MacTechFooter` does not use `bg-[#0A0A0A]`. It uses a token-based class (`bg-card border-border`, or a paper-100 equivalent).
6. `apps/web/lib/utils.ts` exports `cn(...inputs: ClassValue[])` (clsx + tailwind-merge).
7. `apps/web/components/ui/` exists as a directory with at least `button.tsx`, `badge.tsx`, `card.tsx` shaped per shadcn conventions (forwardRef, `cva` variants, `cn` for class merging).
8. `Kpi`, `Badge`, `Pillar` callers are unchanged in shape (no breaking API). The internal `tones` map references `bg-success/15 text-success`-style classes (or equivalent token classes), not literal Tailwind palette names.
9. Contrast ratio ≥ 4.5:1 for all body copy and ≥ 3:1 for badges/KPIs on every background (paper-50, paper-100, white card, paper-200 borders). Spot-check: `text-muted-foreground` on `bg-card` and on `bg-background`.
10. Dashboard at 1440 wide, 1024 wide, 768 wide, and 375 wide does not introduce horizontal scroll. ComingUpRail collapses cleanly to a single column at <1024.
11. `:focus-visible` outline is visible on every primary action (sidebar links, sign-in submit, KPI links, "Add to pipeline").
12. `Term`/`TermPopover`/`ExplainRail` continue to function unchanged on `/opportunities/[id]` and any pursuit detail.
13. `MacTechFooter` `APPS` array still includes `clearD`, `CaptureOS`, `Compliance`, `Training`, `Quality` (cross-suite navigation still works).
14. No new `dark:` Tailwind variants introduced (this is a light-first port).
15. No emoji rendered in any non-error UI string. Greeting comma OK; ❤️/✨/🚀/✅/⚠️ NOT OK. (Existing usage of `↻`, `✕`, `→`, `·` is fine — those are pure typographic glyphs, not emoji.)

## 11. Open questions for the human

1. **Scope of "gold copy."** Is this iteration the *authenticated app only*, or do you want `app/page.tsx` (marketing landing) and the auth shells re-skinned in the same pass? My §7 ranks all three; if Phase 1 is strictly internal, leverage point #6 can be deferred.
2. **Token contract direction.** Do you want this tightly mirrored on vetted's exact var names (`--background`, `--card`, etc.) so future cross-suite components literally drop in unchanged? Or do you want CaptureOS-specific names (`--paper`, `--ink`, `--brand`) to keep the editorial language? My recommendation in §6/§7 assumes the former — same names, different values — because that's what makes the "gold copy" idea actually pay off.
3. **Footer parity.** Vetted lists `clearD` as the first app; CaptureOS's footer doesn't list `clearD` yet. Should the CaptureOS footer's `APPS` array be updated to include `clearD` in this pass? (Trivial change; just want sign-off.)
4. **Pillar color tokens.** The `Pillar` component maps four founder pillars to four hardcoded colors. Should those become first-class tokens (`--pillar-security`, `--pillar-infrastructure`, `--pillar-quality`, `--pillar-governance`) so the next MacTech app reuses them, or should they stay component-local? I'd promote them; want to confirm.
5. **GitHub MCP not connected.** I could not pull issues/PRs labeled `ux`/`design`/`branding` to validate user-reported pain points. If you can connect the MCP for ~10 minutes, I can re-run §4 and refine §7 priority order before the architect picks the 3–7 to ship.

## 11. Human responses (auto-mode decisions)

Auto mode active — answers chosen by the orchestrator from CLAUDE.md context and the brief's recommendations:

1. **Scope of "gold copy."** Full pass: token contract + auth shells + footer + marketing landing + dashboard token migration. The user said "turn this website into our new Gold copy" — interpret as the entire `apps/web/` surface, bounded by §8 non-goals (no domain-card rewrites, no dark mode, no marketing page templates).
2. **Token contract direction.** Mirror vetted's exact var names (`--background`, `--foreground`, `--card`, `--primary`, etc.) so future cross-suite components drop in unchanged. CaptureOS's editorial direction is preserved by the *values* (warm-paper, brand-teal), not by renaming the *variables*. This is the entire point of the gold-copy port.
3. **Footer parity.** Yes — add `clearD` to the CaptureOS footer's `APPS` array so the cross-suite hop is symmetric.
4. **Pillar color tokens.** Promote to first-class tokens: `--pillar-security`, `--pillar-infrastructure`, `--pillar-quality`, `--pillar-governance`. The `Pillar` component reads them via tailwind utilities so the next MacTech app reuses them.
5. **GitHub MCP not connected.** Skip the issue/PR pull. Proceed with code-evidence priorities from §7.

**Architect's selected leverage points for this iteration (3–7 cap):**
- §7.1 — Token contract (HSL CSS vars in `globals.css` + Tailwind mapping)
- §7.2 — Auth pages re-skin (warm-paper)
- §7.3 — Footer re-skin (warm-paper variant) + `clearD` in APPS array
- §7.4 — `lib/utils.ts` `cn()` + minimal `components/ui/` shadcn primitives (button, badge, card) — partial: scaffolding only, do not migrate every primitive
- §7.6 — Marketing landing (`app/page.tsx`) restyle to warm-paper
- §7.7 — Semantic tone tokens (`--success`, `--warning`, `--destructive`) wired through `Kpi`/`Badge` `tones` maps, callers unchanged
- §7.9 — Standardize `--radius`, `--font-mono`, `tabular-nums` defaults

Deferred for next pass (out of scope this iteration): §7.5 shell extraction, §7.8 design-system doc, §7.10 `.card-modern` lift utility.
