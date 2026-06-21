# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Frontend for the Heimwende Energy Advisor — a Vite + React + TS + Tailwind SPA. It only ever talks
to the FastAPI backend; no secrets and no money math live here (see the root and `apps/backend`
CLAUDE.md for the contract and domain rules).

## Commands

Run from `apps/frontend/`:

```bash
pnpm install
pnpm dev          # Vite dev server → http://localhost:5173
pnpm build        # tsc -b && vite build  (type-check is part of the build)
pnpm lint         # eslint . --ext ts,tsx
pnpm typecheck    # tsc --noEmit
```

There is no unit-test setup; `pnpm typecheck` + `pnpm lint` are the only static gates.

## Environment

Two `VITE_*` vars (Vite inlines `VITE_*` into the public bundle, so never put a secret here):

- `VITE_API_BASE_URL` — backend origin, defaults to `http://localhost:8000` if unset (`src/lib/api.ts`).
- `VITE_MAPBOX_TOKEN` — **required** for the globe, address autocomplete, and roof-draw map.
  **Gotcha:** it is declared in `src/vite-env.d.ts` and read in `globe-background.tsx` /
  `mapbox-geocode.ts`, but is *missing from `.env.example`*. Without it the map silently renders an
  error state. Add it to your `.env`.

## Package manager gotcha

The repo registers this app in the root `pnpm-workspace.yaml`, but **both** `pnpm-lock.yaml` (root)
and a local `package-lock.json` exist. Prefer `pnpm`. Adding dependencies is risky because of this
split — that's why `src/lib/zod-resolver.ts` is hand-rolled instead of pulling in
`@hookform/resolvers`. Avoid adding new deps unless necessary.

## The contract seam

`src/lib/types.ts` is the **FROZEN CONTRACT (F02)** — hand-authored TypeScript mirroring
`specs/api/openapi.yaml` exactly. Do **not** edit it without a PR that bumps `openapi.yaml` in the
same commit. It is meant to be regenerated with `make gen-client` (from the repo root). The key
domain semantics encoded in its doc comments:

- `Recommendation.alternatives[]` is the **four-rung cumulative** savings ladder in order
  ☀️→🔋→♨️→🚗. Per-layer "+€/mo" in the configurator =
  `alternatives[n].monthly_saving_eur − alternatives[n-1].monthly_saving_eur` — no extra API call.
- `Recommendation.tiers[]` is the **three packaged offers** (`Tier`, ordered low → middle → high)
  derived from the ladder for the dashboard offer cards (F27). Each `Tier` is self-contained — its €
  figures are copied from a `ScenarioResult` (referenced by `scenario_id`), never recomputed here.
- `explanation_md` / `proposal_copy_md` are LLM prose and are **never** the numeric source of truth.

`src/lib/api.ts` is a tiny hand-written fetch client (TODO: replace with the F02-generated client).
`postRecommend` accepts a `{ fixture }` option that becomes `?fixture=<name>` — and in DEV mode the
intake flow automatically passes `fixture: "demo-detached"` so the UI works **without a running
backend**.

## Architecture

`main.tsx` wraps `App` in a TanStack Query `QueryClientProvider`. **`React.StrictMode` is
intentionally omitted** — its dev double-mount churns Mapbox GL's WebGL context (see the comment in
`main.tsx`). `vite.config.ts` dedupes `react`/`react-dom` to avoid the dual-React "Invalid hook
call". Path alias `@` → `./src` (set in both `vite.config.ts` and `tsconfig.json`).

`App.tsx` renders `IntakeScreen` with a `LandingPage` overlay on top until the user clicks start.

**`features/intake/IntakeScreen.tsx` is the core state machine.** It drives a 5-step flow over a
single shared Mapbox map and a Three.js stage:

```
intake → zooming → roof-draw → roof-params → viewing
  (form)  (flyTo)  (draw poly) (pitch/type)  (3D model + activity feed + recommend call)
```

- `features/landing/` — entry overlay.
- `features/intake/` — `IntakeForm` (React Hook Form + Zod via the custom `zodResolver`; the street
  field is a Mapbox geocode autocomplete, plus a demo bill-upload that extracts field suggestions to
  prefill the form) and the `IntakeScreen` orchestrator. `householdSchema.ts` is the Zod schema for
  the `Household` contract type.
- `features/roof/` — `RoofDrawStep` + `useMapboxDraw` (a `@mapbox/mapbox-gl-draw` hook that returns
  the drawn polygon ring; uses `@turf/turf`) and `RoofParamsStep` (roof type + pitch).
- `features/viewer/` — `HouseCanvas` (react-three-fiber / `three`) and `roofGeometry.ts` extrude the
  drawn polygon + params into a live 3D model.
- `features/activity/` — `ActivityFeed`, the streamed per-step progress log shown next to the model.
- `components/` — shared UI (`StepBar`, `globe-background`, `HeimwendeMark`).

On reaching `viewing`, `IntakeScreen.runRecommend()` calls `postRecommend` and renders progress in
the feed + a status pill with the resulting €/month figure. The pill's "View offers" button
(or "Skip to offers" before a recommendation arrives) opens the offer page.

- `features/offer/` — `OfferResultPage`, the **three-tier dashboard** (low / middle / high) built on
  `Recommendation.tiers`. This is the one post-recommendation screen wired into the flow today (toggled
  by `showOfferPage` in `IntakeScreen`). `demoOfferRecommendation.ts` is a hard-coded `Recommendation`
  used as a fallback so the page renders without a backend (and powers "Skip to offers").

**Built but not yet wired into the live flow:** `features/dashboard/`, `features/results/`,
`features/configurator/`, `features/proposal/`. They consume the `Recommendation` contract but are
not reachable from `App.tsx` today. Wire these in when implementing the remaining
post-recommendation screens (F20–F23).

> The local `README.md` is stale (it describes `App.tsx` as a "hero placeholder + API health badge").
> Trust this file and the source over it.
