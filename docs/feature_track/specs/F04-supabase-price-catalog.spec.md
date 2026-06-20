---
id: F04
title: Supabase schema + price_catalog + reference seed
epic: E0 Foundations
owner: Zhou
reviewers: [Lukas]
priority: P0
mvp: true
status: Ready
branch: feat/F04-supabase-price-catalog
depends_on: [F01]
contract_impact: none
estimate_h: 1.5
---

# F04 — Supabase schema + price_catalog + reference seed

> **North-Star link:** Every euro in the headline `monthly_saving` enters through `price_catalog` — PV/
> battery/HP/wallbox capex and every €/kWh — read at request time and injected into the pure engine.
> Seeding it (plus `reference_plz`) is what makes the demo number reproducible **offline**, with zero
> hard external dependencies.

## 1. Intent (what & why)

Create the §14.3 Supabase (Postgres) schema and seed it so the demo runs fully offline. The centrepiece
is **`price_catalog`** — the §12 DB-driven price table that enforces the rule **"no price is ever
hard-coded in code; all read from here"**. Seed `price_catalog` with the §12 values (each with a `source`
label) and seed `reference_plz` for the demo PLZ(s). Live PVGIS/SMARD remain upgrade toggles backed by the
cache tables. Refs §12, §14.3, §10.

## 2. Scope

**In scope**
- Create the §14.3 tables: `reference_plz`, `price_catalog`, `cache_pvgis`, `cache_dynprice`, `advise_run`, `proposal`, `denkmal_seed`, `mastr_seed`.
- Seed `price_catalog` with all §12 seed rows, each carrying a `source` label and `valid_from` (§12, §10).
- Seed `reference_plz` for the demo PLZ(s) (lat, lon, specific_yield, retail_price, grid_fee, climate_zone, mastr_count) so the resolver has offline data (§14.3, §10).
- Seed `denkmal_seed` / `mastr_seed` for the demo PLZ(s) (heritage flag, neighbour count) — Site-Check social proof (§4, §14.3).
- Offline-safe: the demo has **zero hard external deps**; live PVGIS/SMARD are toggles using `cache_pvgis` (TTL 30d) / `cache_dynprice` (TTL 1d) (§13.2, §14.3).

**Out of scope** (explicitly, to prevent creep)
- The resolver that *reads* `price_catalog` and builds `PricingContext` → **F12**.
- PVGIS / dynamic-tariff adapters that *populate* the cache tables → **F13 / F14**.
- Persisting actual runs/proposals (writes to `advise_run`/`proposal`) → **F17 / F23** (F04 only creates the tables).
- Per-PLZ grid-fee overlays beyond the seeded demo PLZ(s) (Netztransparenz import) → resolver stretch (F12).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | Create `reference_plz (plz PK, lat, lon, specific_yield, retail_price, grid_fee, climate_zone, mastr_count)`. | §14.3 |
| R2 | Create `price_catalog (component, tier, unit, unit_price, source, valid_from, PRIMARY KEY (component, tier, valid_from))`. | §12, §14.3 |
| R3 | Create `cache_pvgis (lat, lon, tilt, azimuth, kwp, payload_json, fetched_at)` — TTL 30d. | §14.3 |
| R4 | Create `cache_dynprice (market_area, day, payload_json, fetched_at)` — TTL 1d. | §14.3 |
| R5 | Create `advise_run (id PK, household_json, options_json, recommendation_json, created_at)` and `proposal (id PK, advise_run_id FK, copy_md, created_at)`. | §14.3 |
| R6 | Create `denkmal_seed (plz, flag)` and `mastr_seed (plz, count)`. | §14.3 |
| R7 | Seed `price_catalog` with all §12 rows, each with a non-null `source` label and a `valid_from`. | §12 |
| R8 | Seed `reference_plz` for the demo PLZ(s) with physics/grid values from §10. | §10, §14.3 |
| R9 | The whole seed runs offline (no network) and is idempotent/re-runnable. | §13.2, §15 |

## 4. Data, formulas & sources

> This feature is the **home of the prices**. The seed rows below are copied verbatim from §12; each
> gets a `source` label. **No price is hard-coded in application code — all read from this table (§12).**

| component | tier | unit_price | source note (label) |
|---|---|---|---|
| `pv_per_kwp` | SMALL | €1,450 | market quote avg; 0 % VAT (§12) |
| `pv_per_kwp` | LARGE | €1,300 | economies of scale (§12) |
| `battery_per_kwh` | — | €700 | usable-kWh market avg (§12) |
| `heatpump_fixed` | — | €22,000 | air-source incl. install, range 18–30k (§12) |
| `wallbox_fixed` | — | €1,200 | incl. install (§12) |
| `oil_per_litre` | — | €1.10 | Destatis heating-oil index (§12) |
| `gas_per_kwh` | — | €0.115 | Destatis gas index (§12) |
| `petrol_per_litre` | — | €1.85 | Destatis / ADAC (§12) |
| `diesel_per_litre` | — | €1.75 | Destatis / ADAC (§12) |
| `retail_per_kwh` | — | €0.37 | Destatis (per-PLZ grid-fee overlay) (§12) |
| `feedin_per_kwh` | — | €0.0778 | Bundesnetzagentur EEG (§12) |
| `public_charge_per_kwh` | — | €0.45 | public CPO avg, L4 Case B baseline (§12) |

`reference_plz` seed values per §10 (physics/grid constants; **prices live in `price_catalog`, not here**):

| Quantity | Value | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `specific_yield` | fallback **980** kWh/kWp (live PVGIS toggle) | PVGIS (EU JRC) | const 980 | L1 · annual_yield (resolver→F12) |
| `retail_price` | €0.37 + per-PLZ grid fee | Destatis/BNetzA | flat €0.37 | L1–L4 · import cost (F12) |
| `grid_fee` | per-PLZ overlay | Netztransparenz/BNetzA | included in €0.37 | resolver overlay (F12) |
| `mastr_count` | seeded neighbour count | MaStR Gesamtdatenexport | ⚪ unknown | Site-Check social proof (F15) |

```
# Schema (§14.3), verbatim:
price_catalog(component, tier, unit, unit_price, source, valid_from,
              PRIMARY KEY (component, tier, valid_from))
# Flow (§12): resolver reads price_catalog (+ per-PLZ overlays) → builds PricingContext → injects into the pure engine.
# Capex (§6.1 Δ_capex) and every €/kWh in Layers 1–4 come from here. Changing a price = one DB row, no redeploy.
```

> **Labelled assumption:** §12/§10 do not name a concrete demo PLZ value, so the exact demo PLZ(s) (and
> their lat/lon, picked to satisfy D3 Germany-only + D7 Denkmal Bavaria option) are a **labelled
> authoring choice** for the seed — documented in the seed file, not invented as a "source".

## 5. Contract surface

`contract_impact: none`. F04 touches no `specs/api/openapi.yaml` schema. It defines storage that the
resolver (F12) reads and endpoints (F17) write; the wire contract is unaffected.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1** — Given a fresh Supabase/Postgres, when the schema migration runs, then all eight §14.3 tables exist with the specified columns and `price_catalog`'s composite PK `(component, tier, valid_from)`.
- [ ] **AC2** — Given the seed has run, when `price_catalog` is queried, then all **12** §12 rows are present with the exact `unit_price` values in §4 and a non-null `source` label on every row.
- [ ] **AC3 (no hard-coded price guard)** — Given the application code, when grepped for the seeded numeric literals (e.g. `1450`, `700`, `22000`, `0.0778`, `0.37`, `0.45`), then none appear hard-coded in engine/adapter code — every price is read from `price_catalog` (§12).
- [ ] **AC4** — Given the seed, when `reference_plz` is queried for a demo PLZ, then a row returns with `lat`, `lon`, `specific_yield` (fallback 980), `retail_price` (€0.37 + grid_fee), and `mastr_count`.
- [ ] **AC5 (offline / demo-safety)** — Given **no network**, when the seed + a read of `price_catalog` and `reference_plz` run, then both succeed (zero external dependency), per §13.2/§15.
- [ ] **AC6 (honesty/edge — idempotent + valid_from)** — Given the seed is run twice, when re-run, then it does not duplicate or error (idempotent), and a price lookup picks the row by `valid_from` so a future price edit is one new row, no redeploy (§12).

## 7. Test plan

- **Unit** (schema/seed, no app I/O): assert table DDL matches §14.3; assert the 12 `price_catalog` rows + `source` labels; assert `reference_plz` demo row.
- **Integration / contract**: a thin "load PricingContext shape" read test proving F12 can select prices by `(component, tier, valid_from)` (the resolver itself is F12).
- **Demo-safety**: run the seed and the reads with networking disabled (AC5); confirm the demo path needs no live PVGIS/SMARD (those are toggles backed by `cache_pvgis`/`cache_dynprice`).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F01** (the `apps/api` app + env to hold the Supabase service-role key, which stays server-side per §11).
- **Downstream (feeds):** **F12** (resolver reads `price_catalog` + `reference_plz` → `PricingContext`), **F13/F14** (write `cache_pvgis`/`cache_dynprice`), **F15** (reads `denkmal_seed`/`mastr_seed`), **F17/F23** (write `advise_run`/`proposal`). Backlog §5 (§12, §14.3 rows).
- **Mock until ready:** consumers blocked on F04 mock `PricingContext` as in-memory constants matching the §12 seed (the same numbers in §4), then swap to the DB read once F04 lands.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Hard-coded prices drift | All prices in `price_catalog` (§12); AC3 greps code for seeded literals; one DB edit, no redeploy (§15). |
| Live API flaky on stage | Seed everything offline (AC5); PVGIS/SMARD are toggles backed by cache tables; `?fixture` golden payloads via F24 (§15). |
| Supabase service-role key leaks | Key lives **only** in FastAPI env, never in the Vite bundle (§11, §1) — enforced by F01's env hygiene. |
| Existing-equipment double-count via wrong seed | F04 only seeds prices/constants; the delta-only capex logic is the engine's (F06–F09) per §3.2 — F04 doesn't model households. |
| Demo PLZ value unverified | Demo PLZ + lat/lon are a **labelled assumption** in the seed file (§4 note), not presented as an official figure. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (schema + seed + offline read).
- [ ] Lint + type-check clean for migration/seed code (`ruff`+`mypy`).
- [ ] Contract honored — `contract_impact: none`; no `openapi.yaml` change.
- [ ] No secret added to the frontend bundle (service-role key server-side only); **no hard-coded price** — all read from `price_catalog` (AC3, §12).
- [ ] Every figure traces to a source or a labelled assumption — every `price_catalog` row has a `source`; demo PLZ is a labelled assumption.
- [ ] Reviewed by Lukas (who signs off the §12 values per Backlog §1); merged to `main`; main is green.
- [ ] The demo happy-path runs **offline** (seed read succeeds with no network) after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §12 (`price_catalog` + seed values), §14.3 (Supabase schema), §10 (reference constants + "used in"), §13.2 (offline/no-key demo selection), §11 (keys server-side), §15 (demo-safety).
- Backlog `FEATURE_BACKLOG.md` §3 E0 row F04, §5 (§12/§14.3/§10 traceability), §6 (live-API-flaky risk).
- `specs/api/openapi.yaml` (F02) — unaffected; consumers are F12/F15/F17.
