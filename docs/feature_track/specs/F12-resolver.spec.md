---
id: F12
title: Resolver (PLZ → context + PricingContext)
epic: E2 Backend & Adapters
owner: Zhou
reviewers: [Lukas]
priority: P1
mvp: true
status: Ready
branch: feat/F12-resolver
depends_on: [F04]
contract_impact: reads
estimate_h: 2
---

# F12 — Resolver (PLZ → context + PricingContext)

> **North-Star link:** The resolver is the **seam between DB prices and the pure engine** — it reads
> `price_catalog` and `reference_plz`, builds a `PricingContext`, and injects it so every euro in the
> headline `monthly_saving` enters through one place. Without it the engine has no prices and no site.

## 1. Intent (what & why)

Turn a household's **PLZ** into the enriched, ready-to-compute context the pure engine consumes:
`lat/lon/retail_price/grid_fee/specific_yield` from `reference_plz`, plus a **`PricingContext`** built
from `price_catalog` (§12) — every €/kWp, €/kWh and €-fixed price the engine needs, **injected, never
imported**. It also produces the **labelled assumptions** for any value that fell back to a default, so
the confidence band (F11) and UI (F23) can surface them. All I/O lives here; the domain stays pure
(§2, §11, §12).

## 2. Scope

**In scope**
- PLZ lookup in `reference_plz` → `lat, lon, specific_yield, retail_price, grid_fee, climate_zone, mastr_count` (§14.3, §11).
- Apply the **per-PLZ grid-fee overlay** onto retail price: `retail_price = base_retail + grid_fee` (§10, §12).
- Read `price_catalog` (by `component, tier, valid_from`) → assemble a typed **`PricingContext`** (all §12 components) injected into the engine (§12).
- Emit an enriched household model + a list of **labelled assumptions** for every fallback used (e.g. "specific yield 980 (fallback)", "flat retail €0.37 (no PLZ overlay)") (§3.4).
- Fallbacks: unknown PLZ → flat retail **€0.37**, specific yield **980**, `mastr_count` ⚪ unknown (§10, §11).

**Out of scope** (explicitly, to prevent creep)
- The §14.3 schema + seed itself → **F04** (this feature only *reads* it).
- The live PVGIS / SMARD fetches that populate caches → **F13 / F14** (resolver returns the fallback `specific_yield`/spread unless those adapters are toggled on).
- The Site-Check permit/feasibility flags → **F15** (resolver supplies `lat/lon`+`mastr_count`; F15 does the OSM/Denkmal/permit logic).
- Per-PLZ grid-fee CSV import beyond the seeded demo PLZ(s) (Netztransparenz bulk import) → **stretch** (use the seeded overlay/flat fallback for the demo).

## 3. Functional requirements

| # | Requirement | Source (§) |
|---|-------------|------------|
| R1 | Given a 5-digit PLZ, look up `reference_plz` and return `lat, lon, specific_yield, retail_price, grid_fee, climate_zone, mastr_count`. | §14.3, §11 |
| R2 | Compute effective `retail_price = base_retail + grid_fee` (per-PLZ overlay); flat **€0.37** if no overlay/unknown PLZ. | §10, §12 |
| R3 | Read `price_catalog` for every §12 component (resolving `tier` and latest `valid_from`) and build a typed `PricingContext`. | §12 |
| R4 | Inject `PricingContext` into the pure engine; the engine **imports no price** (purity preserved). | §2, §12, §1 |
| R5 | Emit a `labelled_assumptions[]` entry for every value served from a fallback (yield 980, flat retail, ⚪ mastr). | §3.4, §7 |
| R6 | Unknown PLZ degrades gracefully (flat retail, yield 980, ⚪ social proof) — never blocks the result. | §3.4, §11 |
| R7 | All I/O (DB reads) lives in the resolver adapter; it returns plain data to the domain. | §2 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> **No price is hard-coded** — every monetary value is read from `price_catalog` (§12) and carried in
> `PricingContext`. This table maps each read to its source and fallback; the prices' own sources live
> on each `price_catalog` row (seeded in F04).

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `lat, lon` | `reference_plz` lookup by PLZ | seeded (§14.3) | — (PLZ mandatory) | L1 · PVGIS coords; F15 · OSM/MaStR |
| `specific_yield` | `reference_plz.specific_yield` | PVGIS (EU JRC) (§10) | const **980** kWh/kWp | L1 · fallback annual_yield |
| `retail_price` | `base_retail + grid_fee` | Destatis/BNetzA (§10) | flat **€0.37** | L1–L4 · import & displaced cost |
| `grid_fee` | per-PLZ overlay | Netztransparenz/BNetzA (§11) | included in €0.37 | resolver · retail overlay |
| `mastr_count` | `reference_plz.mastr_count` | MaStR Gesamtdatenexport (§11) | ⚪ unknown | F15 · neighbour precedent |
| `PricingContext` (all §12 prices) | read `price_catalog` | §12 rows (F04) | seed §12 values | engine · all capex & €/kWh |

```
# Flow (§12), copied verbatim so there is one definition:
#   Resolver reads price_catalog (+ per-PLZ overlays) → builds PricingContext → injects into the pure engine.
# Capex (§6.1 Δ_capex) and every €/kWh in Layers 1–4 come from PricingContext.
effective_retail_price(PLZ) = base_retail(price_catalog 'retail_per_kwh') + grid_fee(reference_plz, PLZ)
# PricingContext components (each a price_catalog row): pv_per_kwp{SMALL,LARGE}, battery_per_kwh,
#   heatpump_fixed, wallbox_fixed, oil_per_litre, gas_per_kwh, petrol_per_litre, diesel_per_litre,
#   retail_per_kwh (overlaid), feedin_per_kwh, public_charge_per_kwh.
```

> **Labelled assumption:** when a PLZ is absent from `reference_plz`, the resolver returns flat retail
> **€0.37**, specific yield **980**, and ⚪ social proof — each emitted as a `labelled_assumptions[]`
> entry (not presented as a measured value), per §3.4.

## 5. Contract surface  *(contract_impact = reads)*

- Reads `Household` (PLZ, address) from `openapi.yaml` (F02). Produces an internal enriched model +
  `PricingContext` consumed by the engine; surfaces into `ScenarioResult` prices and the assumptions
  list (§14.1). No new wire schema object.
- New/changed schema objects: none (read-only seam).
- Backwards-compatible? yes — read-only.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (PLZ enrichment)** — Given a seeded demo PLZ, when resolved, then it returns non-null `lat`, `lon`, `specific_yield`, `retail_price`, `grid_fee`, `climate_zone`, `mastr_count`.
- [ ] **AC2 (grid-fee overlay)** — Given base retail €0.37 and a seeded `grid_fee`, when resolved, then `retail_price == 0.37 + grid_fee` (per-PLZ overlay applied, ±0.001).
- [ ] **AC3 (PricingContext built from DB)** — Given the seed, when the resolver builds `PricingContext`, then all **12** §12 components are present with values equal to the `price_catalog` rows (no literal in code) and the engine receives them by injection.
- [ ] **AC4 (purity preserved)** — Given the engine module, when grepped, then it imports no price/`reference_plz`; the resolver is the only price source (§2, §12).
- [ ] **AC5 (unknown-PLZ fallback)** — Given a PLZ absent from `reference_plz`, when resolved, then `retail_price == 0.37`, `specific_yield == 980`, `mastr_count` is ⚪ unknown, and `labelled_assumptions[]` contains one entry per fallback.
- [ ] **AC6 (worked-example coords feed L1)** — Given the demo household, when resolved and the 980 fallback applies, then `9 kWp × 980 == 8820 kWh` matches the §8 PV-yield input the engine expects.
- [ ] **AC7 (honesty/edge — overlay missing)** — Given a known PLZ with a null `grid_fee`, when resolved, then `retail_price == 0.37` (overlay degrades to flat) and an assumption is labelled.

## 7. Test plan

- **Unit** (resolver logic with an in-memory/stub DB): AC2 overlay math, AC3 `PricingContext` assembly, AC5/AC7 fallback labelling; assert the §8 demo PLZ yields 8,820 kWh via the 980 fallback (AC6) as a named fixture.
- **Integration / contract**: read against the seeded F04 tables; assert `PricingContext` keys/types match what F06–F11 consume; assert no price literal in engine code (shared AC4/F04-AC3 grep).
- **Demo-safety**: resolve a demo PLZ with **no network** — all values come from `reference_plz`/`price_catalog`; live PVGIS/SMARD stay off (§13.2, §15).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F04** (`reference_plz`, `price_catalog`, seeds) and the Supabase service-role key in FastAPI env (§11).
- **Downstream (feeds):** **F06–F11** (engine — `PricingContext` + running-state prices), **F13** (uses `lat/lon` + `specific_yield` fallback), **F15** (uses `lat/lon` + `mastr_count`), **F17** (calls the resolver first in the pipeline).
- **Mock until ready:** consumers mock `PricingContext` as in-memory constants matching the §12 seed (same numbers as F04 §4) and a demo `reference_plz` row, swapping to the real read when F12 merges.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Hidden price import breaks engine purity | All prices injected via `PricingContext`; AC4 greps engine for price literals/imports (§12, §2). |
| Unknown PLZ blocks the demo | Flat €0.37 / yield 980 / ⚪ fallbacks, each a labelled assumption (AC5); never blocks (§3.4). |
| Per-PLZ grid fee unverified | `grid_fee` seeded for demo PLZ(s); flat fallback otherwise; live Netztransparenz import is stretch (§11). |
| Service-role key leak | Key lives **only** in FastAPI env, never in the Vite bundle (§11, §1). |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (overlay math, `PricingContext` assembly, fallbacks).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored — `contract_impact: reads`; no `openapi.yaml` change.
- [ ] No secret in the frontend bundle; **no hard-coded price** — all read from `price_catalog` via `PricingContext`.
- [ ] Every figure traces to a source or a labelled assumption (fallbacks are labelled, not invented).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] Demo happy-path still works end-to-end (resolve → engine) after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §2 (pipeline — resolver is an adapter), §11 (data sources, keys server-side), §12 (`price_catalog` → `PricingContext` flow), §10 (reference constants), §14.3 (Supabase schema), §3.4 (labelled assumptions).
- Backlog `FEATURE_BACKLOG.md` §3 E2 row F12, §5 (§11/§12/§10 traceability).
- `specs/api/openapi.yaml` (F02) · `specs/domain/savings-engine.spec.md` (F03) · F04 (storage read).
