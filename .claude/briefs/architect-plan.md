# Architect Plan
For brief: 2026-05-08T21:30:00-07:00
Iteration: 2 (this pass)

## Items I will address this pass

1. **§5.3 — Single STAGE_TONE/STAGE_LABEL/STAGE_ORDER source.**
   - Existing `lib/pursuits.ts` has `"use server"` directive — can't host plain constants.
   - **Deviation**: place pursuit-stage constants in new file `lib/pursuit-stages.ts`. Document in change log.
   - Update `pipeline/page.tsx`, `opportunities/[id]/page.tsx`, `pursuits/[id]/page.tsx` to import from there.
   - Remove the 🚩 emoji from `recompetes/page.tsx`.

2. **§5.4 — `<BackLink>` primitive + replace inline opportunity-detail header.**
   - Add `<BackLink>` to `components/ui.tsx`.
   - Use on opportunity detail, pursuit detail, draft detail.
   - Replace opportunity detail's inline header with `<PageHeader display>` + `<BackLink>`.

3. **§5.1 — Unify primary-action color.**
   - Extend the legacy `<Button>` in `components/ui.tsx` with `success` / `warning` / `destructive` variants.
   - Migrate `bg-neutral-900`, `bg-amber-700`, `bg-emerald-600`, `bg-red-600` button-style class strings on every authenticated page.
   - Won/lost markers use `success` / `destructive`.

4. **§5.6 + §4.10 — Token migration on dashboard, pipeline, opportunity-detail + sidebar.**
   - Apply the canonical mapping from the brief on each of those three files.
   - Sidebar active state.

5. **§5.2 — Wrap bare jargon with `<Term>` / `<TermPopover>`.**
   - Pages: `/pipeline`, `/library`, `/drafts`, `/forecasts`, `/recompetes`, `/events`, `/settings`.
   - Plus 4 dashboard KPI tiles.
   - Each page needs ≥3 `<Term>`/`<TermPopover>` callsites.
   - Pages without ExplainRail wired use `<TermPopover>`; opportunity detail / pursuit detail keep `<Term>`.

6. **§5.5 — EmptyState standardization on `/forecasts` and `/events`.**
   - `/forecasts` — wrap `<IntegrationDiagnostic>` in `<details>` accordion BELOW a real `<EmptyState>`.
   - `/events` — replace ops-tone body with layman-tone; admin diagnostic fold-out below.

## New primitives introduced

- `BackLink` (in `components/ui.tsx`)
- `STAGE_TONE`, `STAGE_LABEL` re-exports in `lib/pursuit-stages.ts`
- `success` / `warning` / `destructive` Button variants

## Items I am deferring this pass (per brief §11)

- §5.7 pursuit-detail in-page nav
- §5.8 HowItWorks reordering
- §5.9 broader semantic-token migration beyond the 3 hot pages
- §5.10 SummaryStat→Kpi consolidation
- §5.11 full inline-button refactor on detail pages
- §5.12 recompete plan-capture action
