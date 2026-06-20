---
id: F18
title: App shell + TS client + state + API integration
epic: E3 Frontend
owner: Philips
reviewers: [Lukas]
priority: P1
mvp: true
status: Ready
branch: feat/F18-app-shell
depends_on: [F02]
contract_impact: reads
estimate_h: 2
---

# F18 — App shell + TS client + state + API integration

> **North-Star link:** this is the chassis that carries the headline `monthly_saving` to the screen —
> it wires the generated TS client to FastAPI, holds the one `Recommendation` in TanStack Query state,
> and guarantees the demo shows a deterministic number via `?fixture`. No number reaches any other FE
> feature except through this shell.

## 1. Intent (what & why)

Stand up the Vite + React + TS + Tailwind SPA shell that every other frontend feature (F19–F23) plugs
into: routing, the Tailwind design tokens, the **generated TS client** (from the frozen F02 contract)
pointed at `VITE_API_BASE_URL`, TanStack Query for server-state (the `Recommendation`/`SiteCheckResponse`
caches), and **global loading / error / empty states**. It also implements the **`?fixture=<id>` toggle**
so the SPA can render the §8 golden payload without the backend — making every FE feature *mock-first*
and the 90-sec demo (§9) deterministic. This feature computes nothing; it is pure plumbing that defends
the number's path to the UI. Refs §1, §9.

## 2. Scope

**In scope**
- Vite + React + TS scaffold (under `apps/web/`), Tailwind configured with design tokens (the green CTA
  colour, the hero-number type scale), one app font, base layout shell.
- Client-side routing for the demo flow: **Intake → Dashboard** (a single-page configurator dashboard,
  §9), with deep-linkable query params preserved (`?fixture`).
- **Generated TS client** from `specs/api/openapi.yaml` (F02) wired to `VITE_API_BASE_URL`; thin typed
  wrappers for `POST /api/v1/advisor/site-check` and `POST /api/v1/advisor/recommend`.
- **TanStack Query** provider + query/mutation hooks (`useRecommend`, `useSiteCheck`) holding the single
  `Recommendation` as server-state; query-key strategy keyed on household + selection.
- **Global loading / error / empty** UX primitives (skeleton, retry-able error boundary, empty/initial
  state) reused by all FE features.
- The **`?fixture=<id>` toggle**: when present, the client returns the frozen §8 golden payload (served
  by `/recommend?fixture=` from F17/F24, or a bundled JSON fallback) so the SPA renders offline (§1, §15).
- Env hygiene: the build fails if any non-`VITE_API_BASE_URL` secret-shaped var is referenced client-side.

**Out of scope** (explicitly, to prevent creep)
- The intake form & Zod schema → **F19**. The 4 configurator rows → **F20**.
- The hero number / honest curve → **F21**. Buckets / scenarios / up-sell → **F22**.
- Confidence chip / assumptions drawer / proposal / CTA → **F23**.
- Authoring the contract or fixtures → **F02** (TS client source) and **F17/F24** (fixture payloads on the BE).
- Any business math — the SPA only ever calls FastAPI (§1); nothing is computed in the bundle.

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | App is a **Vite + React + TS + Tailwind SPA**; FastAPI is the only server it calls (no Next.js server tier). | §1, D2 |
| R2 | The **only** frontend env var is `VITE_API_BASE_URL`; no key/secret is ever inlined into the bundle. | §1, §15 |
| R3 | All BE access goes through the **generated TS client** from `specs/api/openapi.yaml` (one source of truth), targeting `VITE_API_BASE_URL`. | §1 (contract row) |
| R4 | **TanStack Query** holds server-state; `useSiteCheck` then `useRecommend` mirror the SPA call order (site-check first, then recommend). | §1, §14.2 |
| R5 | Global **loading**, **error (retry-able)**, and **empty/initial** states exist and are reused by F19–F23. | §9 |
| R6 | A **`?fixture=<id>`** query param makes `/recommend` (and the SPA) return the frozen §8 payload deterministically. | §1 (determinism), §15 |
| R7 | Routing covers the demo path Intake → Dashboard; `?fixture` survives navigation so the demo is reproducible. | §9 |
| R8 | CORS-compatible: requests target the configured origin; the app works against the Vite dev origin (`localhost:5173`) and the deployed origin. | §1 |

## 4. Data, formulas & sources

> N/A — pure UI/plumbing. F18 computes no number and reads no price. Every figure it displays arrives
> in the `Recommendation` payload from FastAPI (engine F05–F11 via F17); `price_catalog` lives server-side
> (§12). The only "values" here are config: `VITE_API_BASE_URL` and the `fixture` id.

The one identity the shell must preserve end-to-end so downstream features can rely on it (§14.1, §6.1):
```
monthly_saving = current_monthly_spend − (loan_installment + new_energy_cost)   # carried in ScenarioResult.monthly_saving_eur
layer_delta_eur_month(n) = alternatives[n].monthly_saving_eur − alternatives[n-1].monthly_saving_eur
```
The shell never recomputes these — it transports `Recommendation.alternatives[]` intact to F20/F22.

## 5. Contract surface  *(contract_impact = reads)*

- Reads `specs/api/openapi.yaml` (F02): consumes the generated TS types `Household`, `Recommendation`,
  `ScenarioResult`, `SiteCheckResponse`, and the `?fixture` query param on `/recommend`.
- New/changed schema objects: none (read-only consumer; regenerates the client when F02 bumps).
- Backwards-compatible? Yes — when F02 changes, the client is regenerated in the same commit (Backlog §6);
  the shell compiles against whatever the frozen contract exposes.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (boots as Vite SPA)** — Given the repo, when `pnpm dev` (or `npm run dev`) runs in `apps/web/`,
  then a Vite dev server serves the SPA at `localhost:5173` with Tailwind styles applied and **no Next.js
  server** in the process tree (D2).
- [ ] **AC2 (only VITE_API_BASE_URL)** — Given the built bundle, when grepped for secrets, then **only**
  `VITE_API_BASE_URL` is present and no API key/token/service-role string is inlined (§1, §15).
- [ ] **AC3 (client wired)** — Given `VITE_API_BASE_URL` set, when `useRecommend` runs, then the generated
  TS client POSTs to `${VITE_API_BASE_URL}/api/v1/advisor/recommend` with a `Household` body typed from the
  contract, and the typed `Recommendation` is returned (`tsc` clean).
- [ ] **AC4 (fixture determinism — §8)** — Given `?fixture=demo-detached`, when the dashboard loads with no
  live backend, then it renders the §8 golden `Recommendation` (4 `alternatives`, headline ≈ **+€120/mo**),
  identically on repeat loads.
- [ ] **AC5 (loading/error/empty)** — Given a slow/failed `/recommend`, when the request is pending the
  global **skeleton** shows, on failure a **retry-able error** shows (and retrying re-issues the request),
  and before any intake the **empty/initial** state shows — no crash, no blank screen (§9).
- [ ] **AC6 (call order)** — Given a completed intake, when the dashboard mounts, then `site-check` is
  fetched **before** `recommend` (the SPA calls site-check first, §14.2), both via TanStack Query.
- [ ] **AC7 (honesty/edge — fixture survives nav + a11y)** — Given `?fixture=…`, when navigating Intake↔Dashboard,
  then the param is preserved (demo stays deterministic); and the shell sets a page `<title>`, a single
  `<main>` landmark, and visible focus styles so screen-reader/keyboard users can traverse it.

## 7. Test plan

- **Unit** (component/util, zero network): the `fixture` query-param parser returns the golden payload
  branch; the API-base resolver builds the right URL from `VITE_API_BASE_URL`; the error boundary renders
  a retry affordance.
- **Integration / contract**: with a mocked fetch (MSW) seeded by a §8 fixture decoded from the F02 TS
  types, `useRecommend` returns a `Recommendation` whose `alternatives[].monthly_saving_eur` deserialises;
  assert no field drift vs the generated client.
- **Demo-safety**: `?fixture=demo-detached` renders the full §8 payload **offline** (no `VITE_API_BASE_URL`
  reachable); a build-time check fails the build if a non-`VITE_*` secret is referenced (§1, §15).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F02** (the frozen `openapi.yaml` → generated TS client + the `?fixture` param);
  **F01** (the `apps/web` Vite layout + toolchain). At runtime, **F17** serves `/recommend`/`/site-check`
  and the `?fixture` golden payload; until F17 exists the shell uses a **bundled §8 fixture JSON** so it is
  never blocked on the backend (mock-first, Backlog §6).
- **Downstream (feeds):** **F19** (intake posts a `Household` via the shell's mutation), **F20/F21/F22/F23**
  (all read the single `Recommendation` from TanStack Query state through this shell).
- **Mock until ready:** the shell ships a `?fixture` golden `Recommendation` (the §8 vector) so every FE
  feature codes against the contract types and renders before the backend is live (§1, §15).

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Secret leaks via the Vite bundle | **Only** `VITE_API_BASE_URL` client-side; build-time grep guard; all keys in FastAPI — §1, §15, AC2. |
| Stale Next.js scaffold contradicts D2 | F01 removes `.next/`; F18 boots a pure Vite SPA; AC1 asserts no Next.js server — Backlog §6. |
| FE blocked on the backend | Mock-first: code against the generated client + `?fixture` golden payload; F24 swaps to live with no FE change — §15. |
| Live API flaky in the demo | `?fixture` returns a frozen §8 payload; global error state offers retry — §1, §15. |
| Contract drift between FE and BE | One source of truth (`openapi.yaml`); regenerate the TS client in the same commit on any F02 bump — Backlog §6. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (or a documented manual check for the boot/UX path).
- [ ] Lint + type-check clean (`eslint` + `tsc`).
- [ ] Contract honored — consumes the generated TS client from `openapi.yaml`; no payload drift; client
  regenerated if F02 bumped in the same PR.
- [ ] **No secret added to the frontend bundle** (only `VITE_API_BASE_URL`); no hard-coded price (prices are
  server-side in `price_catalog`).
- [ ] Every figure traces to the payload or a labelled assumption — the shell invents no number.
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] The demo happy-path (`?fixture` renders the §8 dashboard offline) still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §1 (stack, no-secrets, BFF, `?fixture` determinism, CORS), §9 (dashboard target).
- `specs/api/openapi.yaml` (F02 — generated TS client, `?fixture` param) · `specs/domain/savings-engine.spec.md` (§8 vectors via F03).
- Backlog `FEATURE_BACKLOG.md` §3 E3 row F18, §1 (contract is the parallelism seam), §6 (mock-first integration).
