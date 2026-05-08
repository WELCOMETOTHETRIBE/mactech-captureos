# Architect Plan
For brief: 2026-05-08T12:52:40-07:00
Iteration: 1

## Items I will address this pass
Per §11 of the brief (orchestrator's auto-mode decisions): §7.1, §7.2, §7.3, §7.4 (scaffold-only), §7.6, §7.7, §7.9.

## For each item

### §7.1 — HSL token contract in `globals.css` + Tailwind mapping
- Files: `apps/web/app/globals.css`, `apps/web/tailwind.config.ts`
- Approach: Define HSL CSS vars in `:root` (light-first only — no `.dark`). Add Tailwind colors that read `hsl(var(--*))` for `background, foreground, card, popover, primary, secondary, muted, accent, destructive, success, warning, border, input, ring`, plus `--pillar-*`. Keep `paper.*` and `brand.*` legacy palettes intact so existing classes don't break. Add `--font-mono` and `--radius`. Update Clerk autofill rule to use the warm-paper card background instead of obsidian.
- New primitives: none here.
- Risk: Other pages use `border-paper-200`/`bg-paper-50`/`text-brand-700` etc.; preserved as legacy aliases. The `ring DEFAULT` was hardcoded `#207b78` — replaced with `hsl(var(--ring))`.

### §7.2 — Auth pages re-skin
- Files: `apps/web/app/sign-in/[[...sign-in]]/page.tsx`, `apps/web/app/sign-up/[[...sign-up]]/page.tsx`
- Approach: Single column on `bg-background`. White card. Brand-teal primary button. Remove inline hex template strings — Clerk `appearance` references new tokens via Tailwind utility classes only. Keep visible Clerk header (sign-in/up title in our own surface). Remove the dark hero column entirely; replace with a sober paper-100 sidebar containing the trust cues, hidden on mobile.
- Risk: Clerk's appearance map needs to reference real Tailwind classes; arbitrary hex eliminated. Verified by grep §10.3.

### §7.3 — Footer re-skin + clearD added to APPS
- Files: `apps/web/components/footer.tsx`
- Approach: Switch `bg-[#0A0A0A]` → `bg-secondary` (paper-100 equivalent). Add `clearD` as the first entry in the `APPS` array per §11.3. Use `text-muted-foreground`, hover to `text-foreground`.

### §7.4 — `cn()` util + minimal shadcn primitives (scaffolding only)
- Files: new `apps/web/lib/utils.ts`, new `apps/web/components/ui/button.tsx`, new `apps/web/components/ui/badge.tsx`, new `apps/web/components/ui/card.tsx`
- Approach: Install `class-variance-authority`, `clsx`, `tailwind-merge`, `@radix-ui/react-slot` into `apps/web` only. Export `cn(...inputs: ClassValue[])` from `lib/utils.ts`. Build shadcn-shape primitives (`forwardRef` + `cva` + `cn`). Existing `components/ui.tsx` 589-line file remains untouched as legacy aliases — both export shapes coexist.
- Risk: Importers can't accidentally collide because shadcn primitives live in `components/ui/`, the legacy in `components/ui.tsx`. Next/TS resolution: imports of `@/components/ui` continue to resolve to `ui.tsx` (Next prefers files over directories for path resolution by default; verified by build).

### §7.6 — Marketing landing restyle
- Files: `apps/web/app/page.tsx`
- Approach: Use new tokens. Brand-teal eyebrow, italic-serif `display` title using `font-serif italic`, 1-line pitch, "Sign in" primary teal button, "Sign up" ghost button. No grid bg, no glow.

### §7.7 — Semantic tone tokens wired into `Kpi`/`Badge`/`Pillar`
- Files: `apps/web/components/ui.tsx`
- Approach: Update internal `tones` and `valueTones` maps so `tone="amber"` resolves to `warning` token classes, `red` → `destructive`, `green` → `success`, `brand` → `primary`. The component API stays identical. `Pillar` uses `--pillar-*` tokens via Tailwind utilities.

### §7.9 — `--radius`, `--font-mono`, `tabular-nums` defaults
- Files: covered by `globals.css` and `tailwind.config.ts`. Apply `tabular-nums` baseline by adding it to body via globals (defensive — components already opt in for money/score/date columns).

## Items I am deferring this pass
- §7.5 shell extraction — explicitly deferred by orchestrator.
- §7.8 design-system doc — explicitly deferred.
- §7.10 lift utility — explicitly deferred.
- Migrating `components/ui.tsx` callers to the new shadcn primitives. Brief is explicit: scaffolding only this pass. Existing 589-line file keeps working as legacy aliases.
