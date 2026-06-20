---
id: F06
title: Layer 1 — Solar/PV (electricity bucket)
epic: E1 Domain Core
owner: Lukas
reviewers: [Lukas]
priority: P1
mvp: true
status: Ready
branch: feat/F06-layer1-solar
depends_on: [F05]
contract_impact: reads
estimate_h: 2
---

# F06 — Layer 1 — Solar/PV (electricity bucket)

> **North-Star link:** Layer 1 is the **first stacked rung**; it produces the electricity-bucket
> €/mo (`new_energy_cost` reduction) that becomes the gross saving the financing overlay nets against.
> It also raises self-consumption value as later loads stack (§6.2) — the credibility hinge.

## 1. Intent (what & why)

Implement the §5.1 pure module: size the PV array (panels → kWp, existing-PV delta, tier fallback),
take a PVGIS-shaped annual yield, apply **load-aware self-consumption** to split yield into
self-consumed vs exported, value self-consumption at retail price and exports at the EEG feed-in
rate, and emit the electricity bucket €/mo. Deterministic, zero I/O; yield and all prices are
**injected** (PVGIS payload value + `PricingContext`), never fetched here (§2, §12).

## 2. Scope

**In scope**
- Sizing: `panels`, `gross_kwp`, `added_kwp = max(0, recommended_kwp − existing_pv_kwp)`,
  `total_kwp`; tier fallback **SMALL≈6 · MEDIUM≈9 · LARGE≈12 kWp** when no roof geometry.
- Annual yield: accept a PVGIS-shaped input `annual_yield_kwh`; constant fallback
  `total_kwp × specific_yield` with `specific_yield` default **980 kWh/kWp**.
- Load-aware self-consumption: `self_consumed_kwh = autarky_factor × annual_consumption_kwh`
  (capped ≤ `annual_yield_kwh`), `autarky_factor = 0.30` PV-only.
- Valuation: `elec_saving_self` at retail price; `elec_feedin_rev` at **€0.0778/kWh** (EEG ≤10 kWp);
  bucket €/mo output.
- Existing-PV: credit **only incremental** yield's self-consumption + feed-in (no double-count, §3.2).

**Out of scope** (explicitly, to prevent creep)
- Battery uplift of autarky (0.30→~0.60) and arbitrage → F07 (Layer 2).
- HP/EV load accumulation into `annual_consumption_kwh` → F08/F09 add those terms; F06 consumes
  whatever running-state value it is handed.
- The live PVGIS HTTP call + cache + 980 fallback wiring → PVGIS adapter F13; F06 takes the number.
- Capex, subsidies, annuity (0 % VAT) → financing overlay F11.

## 3. Functional requirements

| # | Requirement | Source (§) |
|---|-------------|------------|
| R1 | Size from roof geometry (`usable_roof_m2`, module area/kWp from `price_catalog`) or tier fallback 6/9/12 kWp. | §5.1 |
| R2 | `added_kwp = max(0, recommended_kwp − existing_pv_kwp)`; `total_kwp = existing_pv_kwp + added_kwp`. | §5.1, §3.2 |
| R3 | Use injected `annual_yield_kwh` (PVGIS-shaped); fallback `total_kwp × specific_yield` (980 kWh/kWp). | §5.1 |
| R4 | `self_consumed_kwh = autarky_factor × annual_consumption_kwh`, capped ≤ `annual_yield_kwh`; PV-only autarky 0.30. | §5.1, §8.1 |
| R5 | `exported_kwh = annual_yield_kwh − self_consumed_kwh`. | §5.1 |
| R6 | `elec_saving_self = self_consumed_kwh × retail_price`; `elec_feedin_rev = exported_kwh × 0.0778`. | §5.1, §10 |
| R7 | Bucket €/mo = `(elec_saving_self + elec_feedin_rev) / 12`. | §5.1 |
| R8 | If `existing_pv_kwp > 0`: credit only the **incremental** yield's self-consumption + feed-in. | §5.1, §3.2 |
| R9 | Pure & deterministic; zero I/O; prices and yield injected. | §2, §1, §12 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> No hard-coded prices. `retail_price`, module €/kWp, and `feedin_per_kwh` come from `PricingContext`
> (`price_catalog`, §12). The feed-in **€0.0778/kWh** is a policy rate cited below and read from
> `price_catalog`; this table also pins the physics constants.

| Quantity / call | Value | Official source | Fallback | Used in |
|---|---|---|---|---|
| Annual yield | PVGIS PVcalc `E_y` | EU JRC PVGIS (§11) | `total_kwp × 980` | L1 · annual_yield |
| Specific PV yield (DE) | 980 kWh/kWp | PVGIS (§10) | const 980 | L1 · fallback yield |
| Self-consumption autarky (PV-only) | 0.30 | BSW/HTW Berlin (§10) | const 0.30 | L1 · self_consumed_kwh |
| `retail_per_kwh` | €0.37/kWh (+PLZ grid fee) | Destatis/BNetzA → `price_catalog` (§12) | seed €0.37 | L1 · elec_saving_self |
| `feedin_per_kwh` (≤10 kWp) | **€0.0778/kWh** (1 Feb–31 Jul 2026) | **Bundesnetzagentur** EEG (§10, §6.5) | seed €0.0778 | L1 · elec_feedin_rev |
| Module area · kWp | ≈1.95 m² · ≈0.44 kWp | datasheet → `price_catalog` (§12) | seed 1.95 / 0.44 | L1 · sizing |
| Tier fallback kWp | SMALL 6 · MED 9 · LARGE 12 | §5.1 | — | L1 · sizing |

§5.1 Layer-1 pseudocode, copied **verbatim** so the implementer codes against one definition:
```
# Sizing — from contract package tier, roof geometry, or matched to final-bundle load:
panels        = usable_roof_m2 / module_area_m2          # module_area from price_catalog (≈1.95 m²)
gross_kwp     = panels × module_kwp                      # module_kwp from price_catalog (≈0.44)
added_kwp     = max(0, recommended_kwp − existing_pv_kwp)    # ← existing PV handled here
total_kwp     = existing_pv_kwp + added_kwp
# Tier fallback (no geometry): SMALL≈6 · MEDIUM≈9 · LARGE≈12 kWp

# Annual yield — PVGIS PVcalc (live, official EU JRC), constant fallback:
GET https://re.jrc.ec.europa.eu/api/v5_2/PVcalc?lat=..&lon=..&peakpower=<total_kwp>
    &loss=14&mountingplace=building&angle=<tilt|35>&aspect=<azimuth|0>&outputformat=json
→ annual_yield_kwh = outputs.totals.fixed.E_y            # includes PR/losses
Fallback: annual_yield_kwh = total_kwp × specific_yield(PLZ)   # ≈980 kWh/kWp DE

# Self-consumption is LOAD-AWARE (the key correctness fix — see §8.1):
self_consumed_kwh = autarky_factor × annual_consumption_kwh        # capped ≤ annual_yield
exported_kwh      = annual_yield_kwh − self_consumed_kwh
  # autarky_factor: 0.30 PV-only; rises with battery (L2) and added flexible load (L3/L4)
  # annual_consumption_kwh accumulates across layers: base + HP elec (L3) + EV kWh (L4)

elec_saving_self = self_consumed_kwh × retail_price                 # displaced grid import
elec_feedin_rev  = exported_kwh      × 0.0778                       # ✅ EEG ≤10 kWp (Bundesnetzagentur)
LAYER-1 electricity bucket €/mo = (elec_saving_self + elec_feedin_rev) / 12
# If existing_pv_kwp > 0: credit only the incremental yield's self-consumption + feed-in.
```

> Note: the GET line is shown verbatim from §5.1 for traceability; in F06 the call is **not made** —
> the adapter (F13) performs it and injects `annual_yield_kwh`. F06 stays pure.

## 5. Contract surface  *(contract_impact = reads)*

- Reads `Household` (existing-PV, plz, occupants) and the resolved running-state input
  (`annual_consumption_kwh`, `annual_yield_kwh`, prices) per `openapi.yaml` (F02). Output is part of
  `ScenarioResult.breakdown.electricity_eur_month` (§14.1).
- New/changed schema objects: none (consumes the contract).
- Backwards-compatible? yes — read-only.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (self-consumption split, PV-only)** — Given `annual_consumption_kwh=3081`,
  `annual_yield_kwh=8820`, `autarky=0.30`, when computed, then `self_consumed_kwh ≈ 924.3`
  (0.30×3081) and `exported_kwh ≈ 7895.7` (±1).
- [ ] **AC2 (valuation)** — With AC1 plus retail €0.37 and feed-in €0.0778, then
  `elec_saving_self ≈ €342/yr` (924.3×0.37) and `elec_feedin_rev ≈ €614/yr` (7895.7×0.0778);
  bucket ≈ (342+614)/12 ≈ **€80/mo** — matches the §8 "+€80 Δ gross" Solar rung (±€2).
- [ ] **AC3 (yield fallback)** — Given no PVGIS input and `total_kwp=9`, then
  `annual_yield_kwh == 9×980 == 8820` and the result carries a labelled "specific yield 980 (fallback)"
  assumption.
- [ ] **AC4 (tier fallback sizing)** — Given no roof geometry and tier MEDIUM, then `total_kwp == 9`
  (SMALL→6, LARGE→12 checked too).
- [ ] **AC5 (self-consumption cap)** — Given `annual_consumption_kwh` so large that
  `0.30×consumption > annual_yield_kwh`, then `self_consumed_kwh == annual_yield_kwh` and
  `exported_kwh == 0` (never negative feed-in).
- [ ] **AC6 (existing-PV delta, no double-count)** — Given `existing_pv_kwp=4`, `recommended_kwp=9`,
  then `added_kwp==5`, `total_kwp==9`, and only the **incremental** yield's self-consumption + feed-in
  is credited to this layer (capex on the added 5 kWp handled in F11).
- [ ] **AC7 (honesty/edge — small base load)** — Given the §8 small base load, then the bucket is a
  **modest positive** dominated by cheap feed-in (oversized array exports at 7.78 ct); this is the
  documented "solar alone is mildly net-negative after installment" story (§8) and the value only
  climbs once L3/L4 raise `annual_consumption_kwh` (§6.2).

## 7. Test plan

- **Unit** (pure, zero I/O): AC1–AC7 as vectors; the §8 Solar rung (3,081 kWh load, 8,820 kWh yield →
  ≈+€80/mo gross) as a named golden fixture; determinism + injected-price property test (no value
  imported); cap and existing-PV-delta edge cases.
- **Integration / contract**: output maps to `breakdown.electricity_eur_month` field name/shape from
  the frozen `openapi.yaml`.
- **Demo-safety**: with the 980 fallback yield and seeded `price_catalog` prices, the fixture
  reproduces ≈€80/mo offline — no PVGIS call needed.

## 8. Dependencies & interfaces

- **Upstream (needs):** F05 (`annual_consumption_kwh`, `existing_pv_kwp`, running state); injected
  `annual_yield_kwh` (F13 adapter or fallback) and `PricingContext` (§12).
- **Downstream (feeds):** F07 (battery builds on this electricity bucket and the same yield/autarky),
  F10 (marginal ladder), F11 (financing nets installment against this gross).
- **Mock until ready:** consumers mock the §8 Solar-rung fixture (≈+€80/mo gross) until F06 merges;
  F13 mocked by injecting `annual_yield_kwh = total_kwp × 980`.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Self-consumption ratio not credible → number doubted | load-aware autarky 0.30, cited (BSW/HTW); band shown in F11; §8.1 derivation (§15). |
| Existing PV double-counted | credit incremental yield only; capex on delta (§3.2); AC6 asserts it. |
| Hidden price/yield import breaks purity | both injected; unit tests run with zero network and a stub `PricingContext` (§12). |
| Feed-in rate drift | €0.0778 read from `price_catalog`, sourced to Bundesnetzagentur (§10); one DB edit if it changes. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated unit tests (incl. the §8 +€80 Solar vector).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored: output shape = `breakdown.electricity_eur_month` per `openapi.yaml`; no drift.
- [ ] No secret in any bundle; no hard-coded price (retail/feed-in/module € from `price_catalog`).
- [ ] Every figure traces to a §10 source or a labelled assumption (no invented precision).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] Demo happy-path still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §5.1, §3.2, §6.2, §8, §8.1, §10, §11, §12
- `specs/api/openapi.yaml` · `specs/domain/savings-engine.spec.md` (F03)
