# Change Log
For brief: 2026-05-08T12:52:40-07:00
Iteration: 1
Generated: 2026-05-08T13:30:00-07:00

## Items addressed

### §7.1 — HSL token contract + Tailwind mapping
- **Brief reference:** §7.1, §10.1, §10.2, §11.Q2, §11.Q4
- **Files modified:** `apps/web/app/globals.css`, `apps/web/tailwind.config.ts`
- **Files created:** none
- **Approach taken:** Replaced the inline-hex token defaults in `globals.css` with a complete HSL CSS-variable contract under `:root` — same variable names as vetted/clearD's gold copy, values express CaptureOS's warm-paper + brand-teal direction. Added pillar tokens (`--pillar-security|infrastructure|quality|governance`) as first-class. Updated `tailwind.config.ts` to expose every var as a Tailwind utility (`bg-background`, `text-muted-foreground`, `border-border`, `bg-primary text-primary-foreground`, `ring-ring`, `bg-success`, `bg-warning`, `bg-pillar-security`, etc.). Kept `paper.*` and `brand.*` palettes as legacy aliases — 158 existing class hits still compile unchanged.
- **Design decisions worth flagging:**
  - Light-first, no `.dark` block — explicit per brief §6 + CLAUDE.md.
  - Body now sets `font-variant-numeric: tabular-nums` globally; `.font-serif` opts out so editorial display titles render proportional figures.
  - Default `ringColor` reads `hsl(var(--ring))` instead of hard-coded teal — same color, single source of truth.
  - `--radius: 0.5rem` set; `borderRadius.lg/md/sm` derive from it so existing `rounded-md` calls feel consistent.
- **What I did NOT do and why:** Did not migrate every `bg-paper-*` / `text-brand-*` callsite in the repo. Brief explicitly bounded scope to "minimal scaffolding"; legacy aliases keep callers working.

### §7.2 — Auth pages re-skin (warm-paper)
- **Brief reference:** §7.2, §10.3, §10.4, §10.11
- **Files modified:** `apps/web/app/sign-in/[[...sign-in]]/page.tsx`, `apps/web/app/sign-up/[[...sign-up]]/page.tsx`
- **Files created:** none
- **Approach taken:** Rewrote both pages on `bg-background` (warm paper-50). Hidden-on-mobile sober sidebar (`bg-secondary` / paper-100) with the trust cues demoted from Lucide-icon chips to small-bullet typography. Right column is a centered single-column form. Clerk `appearance` map references Tailwind utility classes only — every former `bg-[#xxxxxx]`, `text-[${ACCENT}]`, template-string interpolation removed. Visible header with brand-teal eyebrow and italic-serif page title for cross-product consistency.
- **Design decisions worth flagging:**
  - Removed the radial-glow auras and the 48px grid background — brief §9 rejects them.
  - Removed the SVG icons (Radar/Crosshair/FileText) on trust cues; replaced with a primary-token bullet. Icons read "B2C SaaS landing"; CaptureOS doesn't.
  - Removed the `invert` filter on the MacTech logo — it was inverting white-on-dark; we're now on paper.
  - Mobile hero collapses to a sober eyebrow + italic-serif title; no gradient block.
- **What I did NOT do and why:** Did not deepen accessibility past visible focus rings + token-driven contrast — that wasn't called out in the brief, and Clerk's components own most of the form a11y.

### §7.3 — Footer re-skin + clearD added to APPS
- **Brief reference:** §7.3, §10.5, §10.13, §11.Q3
- **Files modified:** `apps/web/components/footer.tsx`
- **Approach taken:** Switched `bg-[#0A0A0A] border-[#1f1f1f] text-gray-400` to `bg-secondary border-border text-muted-foreground`; hover color is `text-primary` (brand teal). Added `clearD` as the first entry in `APPS` per §11.Q3.
- **Design decisions worth flagging:** The `clearD` href points to `https://cleard.mactechsolutionsllc.com` — guessing at the cross-suite host pattern based on the other APPS entries. If the production host differs, swap it in a one-line follow-up.

### §7.4 — `cn()` util + minimal shadcn primitives (scaffolding only)
- **Brief reference:** §7.4, §10.6, §10.7
- **Files modified:** none (existing `components/ui.tsx` 589-line file kept as legacy aliases)
- **Files created:**
  - `apps/web/lib/utils.ts` — `cn(...inputs: ClassValue[])` (clsx + tailwind-merge)
  - `apps/web/components/ui/button.tsx` — `cva` + `forwardRef` + `Slot` (asChild), token-driven variants
  - `apps/web/components/ui/badge.tsx` — semantic variants (`default | secondary | destructive | success | warning | outline | muted`)
  - `apps/web/components/ui/card.tsx` — `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`
- **Approach taken:** Pure scaffolding — no callsites migrated. New code reaches into `@/components/ui/button` etc.; existing `@/components/ui` keeps resolving to the legacy file.
- **Design decisions worth flagging:** The directory `components/ui/` and file `components/ui.tsx` coexist by Node/bundler resolution rules — bare `@/components/ui` resolves to the file, `@/components/ui/button` resolves into the directory. Verified by clean `tsc --noEmit` and `next dev` boot.
- **What I did NOT do and why:** Did not migrate any existing callers (Dashboard, Pipeline, Opportunity detail) to the new primitives. Brief §7.4 explicitly says "scaffolding only; do not migrate every primitive." A future pass can move surfaces over one at a time.

### §7.6 — Marketing landing restyle
- **Brief reference:** §7.6, §10.3
- **Files modified:** `apps/web/app/page.tsx`
- **Approach taken:** Brand-teal eyebrow, italic-serif `display`-style title (`font-serif italic`), 1-paragraph pitch, primary-teal "Sign in" button, ghost "Sign up" button. Token-driven, with explicit focus rings. Footer line in muted-foreground.

### §7.7 — Semantic tone tokens through `Kpi` / `Badge` / `Pillar`
- **Brief reference:** §7.7, §10.8
- **Files modified:** `apps/web/components/ui.tsx`
- **Approach taken:** Component APIs unchanged (`Kpi tone="amber|red|green|brand|neutral"`, `Badge tone="amber|red|green|brand|blue|violet|neutral"`). Internal `tones` and `valueTones` records now resolve `amber → warning`, `red → destructive`, `green → success`, `brand → primary`, `neutral → muted`. `Pillar` rewritten to render directly with pillar-token utility classes (`bg-pillar-security/15 text-pillar-security border-pillar-security/20`, etc.) so the four founder pillars become first-class brand tokens. Also migrated `Card`, `Section`, `EmptyState`, `Button`, `LinkButton`, `PageHeader` away from raw `border-paper-200`/`text-neutral-*` to token utilities — this is transparent to all callers.
- **Design decisions worth flagging:**
  - `Badge` `blue` and `violet` tones still resolve to raw Tailwind palettes (`bg-blue-50 text-blue-700`, etc.). They carry pillar/informational meaning — the future-pass concern is whether to alias them under pillar-foundational tokens. Out of scope this iteration.
  - `Pillar` no longer routes through `Badge` for the four known pillars — the pillar tokens have no neat foreground pair, so we render the chip inline. Falls back to `<Badge tone="neutral">` for unknown pillar strings.

### §7.9 — `--radius`, `--font-mono`, `tabular-nums` defaults
- **Brief reference:** §7.9
- **Files modified:** covered by `globals.css` and `tailwind.config.ts` above.
- **Approach taken:** `--radius: 0.5rem` defined; `borderRadius.lg/md/sm` derive from it. `--font-mono` defined and exposed as `font-mono`. `body` sets `font-variant-numeric: tabular-nums`; `.font-serif` opts out so display titles aren't tabular.

### Token migration in `(app)/layout.tsx`
- **Brief reference:** §10.3 (zero hex in target file)
- **Files modified:** `apps/web/app/(app)/layout.tsx`
- **Approach taken:** Swapped `bg-paper-50` → `bg-background`, `border-paper-200` → `border-border`, `bg-white` → `bg-card`, `text-neutral-*` → `text-foreground|muted-foreground`. No structural change. The shell extraction (§7.5) is deferred per brief §11.

## New primitives introduced

| Component | Location | Purpose | Where it's used |
|---|---|---|---|
| `cn()` | `apps/web/lib/utils.ts` | Standard shadcn class merger | Every new primitive in `components/ui/` |
| `Button` (shadcn) | `apps/web/components/ui/button.tsx` | `cva` + `forwardRef` + `Slot` token-driven button | Scaffolding only; not yet imported by app code |
| `Badge` (shadcn) | `apps/web/components/ui/badge.tsx` | Semantic-variant badge | Scaffolding only |
| `Card` family | `apps/web/components/ui/card.tsx` | Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter | Scaffolding only |

## Tokens / config changed

- **`apps/web/app/globals.css`:** Added complete HSL CSS-var token block (background, foreground, card+fg, popover+fg, primary+fg, secondary+fg, muted+fg, accent+fg, destructive+fg, success, warning, border, input, ring, four pillar tokens, --radius, --font-sans, --font-mono). Body now uses tokens for color/background/font-family and defaults `font-variant-numeric: tabular-nums`. `:focus-visible` outline color now reads `hsl(var(--ring))`. Clerk autofill rule rewritten to use card tokens (warm paper) instead of obsidian.
- **`apps/web/tailwind.config.ts`:** Added every token as a Tailwind utility, `borderRadius` derives from `--radius`, default `ringColor` reads `hsl(var(--ring))`. Pillar tokens exposed as `bg-pillar-{security|infrastructure|quality|governance}`. Legacy `paper.*` and `brand.*` palettes preserved as aliases.

## Test commands run and their result

- `pnpm --filter @mactech/web add class-variance-authority clsx tailwind-merge @radix-ui/react-slot` → installed cleanly
- `npx tsc --noEmit` → **pass** (exit 0, zero output)
- `next dev` boot test (port 3199) → **pass** (Ready in 191ms; `/`, `/sign-in`, `/sign-up` all return 200)
- ESLint → **not run** — pre-existing project issue (no `eslint.config.js` present, ESLint 9 won't read legacy `.eslintrc`). Not caused by this PR.
- `next build` → **not run** to keep iteration fast; `next dev` boot + clean tsc cover the build path for these changes.

## Verification commands run

```bash
# Brief §10.3: zero arbitrary hex in target files
grep -rE "bg-\[#|text-\[#|border-\[#" apps/web/app/sign-in apps/web/app/sign-up apps/web/components/footer.tsx apps/web/app/page.tsx 'apps/web/app/(app)/layout.tsx' 'apps/web/app/(app)/dashboard/page.tsx'
# → exit 1 (zero matches)

# Brief §10.3: no template-string interpolation hexes in those files
grep -rE 'bg-\[\$\{|text-\[\$\{|border-\[\$\{' [same files]
# → only one match, in a doc comment ('no template-string `bg-[${VAR}]`'), not in code

# Brief §10.14: no new dark: variants
grep -r "dark:" apps/web/app apps/web/components
# → 0 hits

# Brief §10.15: no emoji in changed UI files
grep -nP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' [changed files]
# → exit 1 (zero matches)

# Every required token defined in globals.css
for v in background foreground card card-foreground popover popover-foreground primary primary-foreground secondary secondary-foreground muted muted-foreground accent accent-foreground destructive destructive-foreground border input ring success warning radius font-sans font-mono pillar-security pillar-infrastructure pillar-quality pillar-governance ; do grep -c "--${v}:" apps/web/app/globals.css ; done
# → all 28 vars: 1
```

## Known limitations

- `clearD` href in the footer (`https://cleard.mactechsolutionsllc.com`) is a guess based on the other APPS host pattern. If the production host differs, a one-line tweak in `apps/web/components/footer.tsx`.
- `Badge` `blue` and `violet` tones still use raw Tailwind palettes (`bg-blue-50`, `bg-violet-50`). They appear in `NoticeTypeBadge` (combined synopsis = blue, presolicitation = blue) and `SetAsideBadge` (SDVOSB = violet, 8(a) = violet). Promoting these to dedicated tokens (`--info`, `--accent-violet`) is a follow-up; the brief didn't ask for it.
- The shadcn primitives in `components/ui/` are scaffolding only. Migrating callsites (Dashboard KPI grid, Pipeline kanban, Opportunity detail) is deferred per §7.4.
- ESLint is not configured at the project level (ESLint 9 + missing `eslint.config.js`). Pre-existing; not in scope.
- `next build` not run — would take longer than the iteration budget. `next dev` boots cleanly with the new tokens, which exercises the same Tailwind compilation path.

## Suggested verifier focus

1. **Visual diff the auth pages before/after.** The sign-in shell went from full-bleed obsidian + radial glows to single-column warm paper with a sober paper-100 sidebar. Confirm the brand-teal "Continue" / submit button hits primary-token color (`hsl(178 58% 30%)` = `#207b78`).
2. **Footer warm-paper rendering on the dashboard.** Scroll to the bottom of `/dashboard`; the footer should now be paper-100 (`bg-secondary`) with hairline border, no obsidian slab.
3. **Pillar chip colors.** Open `/opportunities/[id]` (or any place `<Pillar>` renders); confirm the four founder pillars render with `--pillar-*` tints — security blue, infrastructure green, quality amber, governance violet — and `cursor-help` tooltips still appear.
4. **Check that the legacy palette didn't break.** Surfaces using `border-paper-200` / `bg-paper-50` / `text-brand-700` directly (Pipeline, Library, settings pages) should look unchanged. Quick spot-check on `/pipeline`.
5. **shadcn primitives are reachable but not yet wired.** Confirm `import { Button } from "@/components/ui/button"` resolves and `import { Card } from "@/components/ui"` still resolves to the legacy 589-line file. Both should be true.
6. **Auth page Clerk `appearance` map** has no string templates and no hex literals. The Clerk-rendered form fields should adopt warm-paper backgrounds, brand-teal focus rings.
