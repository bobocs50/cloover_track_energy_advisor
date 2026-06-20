---
id: F08
title: Layer 3 — Heat pump (heating bucket)
epic: E1 Domain Core
owner: Lukas
reviewers: [Lukas]
priority: P2
mvp: true
status: Ready
branch: feat/F08-layer3-heatpump
depends_on: [F05]
contract_impact: reads
estimate_h: 2
---

# F08 — Layer 3 — Heat pump (heating bucket)

> **North-Star link:** computes the **heating bucket €/month** the heat pump adds —
> `baseline_heating_cost − heating_new_cost` — and raises `annual_consumption_kwh`, which lifts the
> self-consumption value of L1/L2, directly moving the headline `monthly_saving` (§5.3, §6.2).

## 1. Intent (what & why)

Layer 3 is a pure module that replaces the household's current heating with a high-SCOP air-source
heat pump and reports the monthly heating-cost reduction on the running state (§5.3). It must serve
**both** offer cases from the §3.2 matrix: **Case A** fossil heating (OIL/GAS) → new HP, and **Case B**
an existing **old/inefficient** HP → efficiency upgrade to a state-of-the-art unit. Both share the
heat-demand and running-cost maths; they differ only in the baseline replaced and the subsidy (the KfW
HP→HP nuance, §5.3/§6.5). It is the literal answer to "still on oil? this layer" (§9).

## 2. Scope

**In scope**
- Heat demand from actual fuel spend (Case A OIL/GAS) or backed out of old-HP electricity (Case B), with the area-method fallback by `building_year × floor_area_m2`.
- `new_SCOP` selection (3.5 Case A / 4.0 Case B), `hp_electricity_kwh`, PV overlap split, `heating_new_cost`.
- Accumulating `hp_electricity_kwh` into `annual_consumption_kwh` so L1/L2 are re-evaluated higher (§6.2).
- Computing the correct baseline per case and the heating bucket €/mo.
- Surfacing the **KfW grant rate distinction** (Case A eligible 50 %, Case B 30 %) as an input/flag to F11 financing (the grant € is applied in F11, not here).

**Out of scope** (explicitly, to prevent creep)
- Subsidy/annuity/capex math and the modelled grant € amount → **F11** (§6.5).
- Buffer-tank load-shift into cheap dynamic-tariff hours → 🔶 stretch (§7.1 "optional, stretch").
- District heating and modern-HP cases (Δ = 0, hidden) — handled as offer gating; here they yield bucket €0.
- Live fuel/retail prices — injected via `PricingContext` from `price_catalog` (§12); never imported here.

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | Case A: compute `heat_demand_kwh` from `heating_eur_month` using OIL (10.0 kWh/L × 0.85 η) or GAS (€0.115/kWh × 0.90 η) per `PricingContext`. | §5.3, §10 |
| R2 | Case B: back out `heat_demand_kwh` from old-HP electricity using `old_SCOP ≈ 2.8` (refine from `existing_heatpump_year`). | §5.3, §10 |
| R3 | Fallback (either case, on missing fuel data): area method `heat_load_W_m2 = lookup(building_year)` → `required_kW` (ceil to 6/8/…/16) → `× 1800` full-load hours. | §5.3, §10 |
| R4 | `hp_electricity_kwh = heat_demand_kwh / new_SCOP`, with `new_SCOP = 3.5` (Case A) or `4.0` (Case B). | §5.3, §10 |
| R5 | `annual_consumption_kwh += hp_electricity_kwh` so L1/L2 self-consumption is re-evaluated on the running state. | §5.3, §6.2 |
| R6 | Split solar coverage: `solar_covered_kwh = hp_electricity_kwh × overlap` with `overlap = 0.15` PV-only / `0.30` +battery; `hp_grid_kwh = hp_electricity_kwh − solar_covered_kwh`. | §5.3, §10 |
| R7 | Baseline replaced = Case A `heating_eur_month`; Case B `heat_demand_kwh / old_SCOP × retail_price / 12`. Bucket €/mo = baseline − `heating_new_cost`. | §5.3 |
| R8 | Emit a `kfw_case` flag: Case A ⇒ eligible for Klima-Geschwindigkeitsbonus (50 %), Case B ⇒ HP→HP, **no Klima-bonus** (30 %). | §5.3, §6.5 |
| R9 | Modern HP / district heating ⇒ Layer 3 not offered, bucket Δ = 0 (consistent with the offer matrix). | §3.2, §6.3 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> Every number cites an official/primary source and a fallback. No hard-coded prices — fuel/retail
> prices come from `price_catalog` (§12) via `PricingContext`; this table holds physics/policy constants.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| Heating oil | 10.0 kWh/L · η 0.85 | Destatis / DIN (§10) | seeded const | L3 · heat_demand (Case A) |
| Gas all-in price · η | €0.115/kWh · 0.90 | Destatis (§10) | seeded const | L3 · heat_demand (Case A) |
| `oil_per_litre` / `gas_per_kwh` / `retail_per_kwh` | €1.10 / €0.115 / €0.37 | `price_catalog` §12 (Destatis/BNetzA) | seeded §12 values | L3 · prices (injected) |
| HP SCOP — new | 4.0 state-of-the-art; 3.5 baseline air-source | manufacturer JAZ / BWP (§10) | 3.5 / 4.0 const | L3 · hp_electricity (both cases) |
| HP SCOP — old (Case B) | 2.8 (age ≥ 12 yr / pre-2014); refine from install year | BWP / field data (§10) | 2.8 const | L3 Case B · old_hp baseline |
| PV→HP overlap | 0.15 PV-only · 0.30 +batt | engineering (§10) | as stated | L3 · solar_covered |
| Heat-load by Baujahr (W/m²) | 150 (<1977) … 40 (>2016) | IWU/TABULA (§10) | table | L3 · area-method fallback |
| Full-load hours (heating) | 1800 h | DE single-family norm (§10) | 1800 const | L3 · area-method fallback |
| KfW 458 grant rate | A: 50 % (base 30 % + Klima 20 %) · B: 30 % (no Klima) cap 70 %/€21k | KfW (official §6.5, D4) | as stated | §6.5 (applied in F11) |

Key formula(s), copied verbatim from §5.3 so the implementer codes against one definition:
```
# Heat demand (kWh/yr) — independent of the current heating system:
#   Case A primary (from ACTUAL fuel spend, most credible):
#     OIL: 10.0 kWh/L gross × 0.85 boiler η = 8.5 kWh useful/L; oil price from price_catalog
#     GAS: ≈ €0.115/kWh all-in × 0.90 η
#     heat_demand_kwh = (heating_eur_month × 12 / fuel_unit_price) × boiler_efficiency × calorific
#   Case B (old HP): back out demand from the old unit's electricity:
#     heat_demand_kwh = (heating_eur_month × 12 / retail_price) × old_SCOP
#       old_SCOP ≈ 2.8 default (age ≥ 12 yrs / pre-2014 air-source); refine from existing_heatpump_year
#   Fallback for either (area method, uses floor_area + building_year):
#     heat_load_W_m2 = lookup(building_year)  # §10 table
#     required_kW = ceil_to(6/8/.../16, heat_load_W_m2 × floor_area_m2 / 1000)
#     heat_demand_kwh = required_kW × 1800 full-load hours

new_SCOP = 3.5 (Case A, conservative air-source) … 4.0 (Case B, state-of-the-art target)
hp_electricity_kwh = heat_demand_kwh / new_SCOP        # Case B deliberately picks the higher SCOP
annual_consumption_kwh += hp_electricity_kwh           # ← raises L1/L2 self-consumption value
solar_covered_kwh  = hp_electricity_kwh × overlap      # 0.15 PV-only · 0.30 +battery (winter-weak)
hp_grid_kwh        = hp_electricity_kwh − solar_covered_kwh
heating_new_cost   = hp_grid_kwh × retail_price / 12

# Baseline that the new HP replaces:
#   Case A: heating_eur_month (current fossil fuel spend)
#   Case B: old_hp_running_cost = heat_demand_kwh / old_SCOP × retail_price / 12   (= current HP elec spend)
LAYER-3 heating bucket €/mo = baseline_heating_cost − heating_new_cost
```
Case B saving driver (the efficiency delta only): `heat_demand × (1/old_SCOP − 1/new_SCOP) × retail_price`.
KfW nuance: HP→HP does **not** earn the Klima-Geschwindigkeitsbonus ⇒ Case B modelled at base **30 %**, not 50 % (§5.3/§6.5).

## 5. Contract surface  *(if contract_impact ≠ none)*

- **Reads only** — `contract_impact: reads`. Consumes `Household` fields frozen in F02: `heating {fuel, eur_month}`, `existing_heatpump_year` (nullable; null ⇒ no HP), `floor_area_m2`, `building_year`.
- New/changed schema objects: none. Output flows through `ScenarioResult.breakdown.heating_eur_month` (existing field, §14.1).
- Backwards-compatible? Yes — no schema change; this feature only reads the F02 contract.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (Case A worked example, §8 — split exact intermediate from illustrative bucket; see DD-1)** — Given the §8 home (€180/mo oil, 3 people, air-source HP, on the running state with PV+battery already ticked), when Layer 3 is added, then:
  - **(exact, DD-1-independent)** `hp_electricity_kwh ≈ 4,769 kWh/yr` (=(180×12/1.10)×8.5/3.5, §8 derived quantities);
  - **(illustrative)** the **heating bucket alone ≈ €77/mo** (baseline €180 − HP grid cost at `overlap = 0.30` +battery: `4,769 × (1−0.30) × €0.37 / 12 ≈ €103` ⇒ `180 − 103 ≈ €77`);
  - the larger **HP-rung Δ gross ≈ €107/mo** is reached **only if ~€30/mo of extra PV self-consumption** that the HP load unlocks is credited to **L1/L2 on the running state** (§6.2). **Per DD-1 (F03 §0), credit that €30 in exactly one place**: under the recommended model it lives in the re-evaluated L1/L2 electricity bucket, so it must **not also** be added to the heating bucket here (which would double-count `solar_covered`). Assert the heating bucket ≈ €77/mo and the running-state L1/L2 lift separately, both ±15 % (illustrative pending DD-1); do not pin a hard €107 here.
- [ ] **AC2 (Case A net, §8 — ILLUSTRATIVE pending DD-1)** — Given AC1 plus the F11 installment €87/mo (€22k − 50 % KfW = €11,000 capex), when net is formed, then the HP rung is **net positive** (illustrative **Δ net ≈ +€20/mo**, ±15 %) and cumulative net moves up toward **≈ −€4** (§8 table). The exact per-bucket euro split is DD-1-dependent; only the sign (positive) and the AC3 exact-sum invariant (F03) are euro-exact.
- [ ] **AC3 (`annual_consumption_kwh` lift, §6.2)** — Given Layer 3 added on the running state, when L1/L2 are re-evaluated, then `annual_consumption_kwh` increases by exactly `hp_electricity_kwh` and the self-consumed kWh of PV/battery rises (no double-count).
- [ ] **AC4 (Case B efficiency upgrade)** — Given `existing_heatpump_year` ⇒ old/inefficient HP (`old_SCOP = 2.8`) and `new_SCOP = 4.0`, when Layer 3 is added, then the saving equals the efficiency delta `heat_demand × (1/2.8 − 1/4.0) × retail_price` and is **smaller** than the equivalent fossil swap.
- [ ] **AC5 (KfW nuance)** — Given Case B (HP→HP), when the `kfw_case` flag is emitted, then it marks **30 %** (no Klima-Geschwindigkeitsbonus); given Case A it marks **50 %** (§5.3/§6.5).
- [ ] **AC6 (fallback)** — Given missing/zero fuel spend, when heat demand is computed, then the area method (`heat_load_W_m2(building_year) × floor_area_m2 / 1000`, ceil to 6/8/…/16 kW, × 1800 h) is used, and the result is flagged as a labelled assumption.
- [ ] **AC7 (honesty/edge — modern HP & overlap)** — Given a modern/efficient HP or district heating, then Layer 3 bucket Δ = 0 (not offered); and given PV-only (no battery), then `overlap = 0.15` (not 0.30) so `solar_covered_kwh` is lower and `heating_new_cost` higher.

## 7. Test plan

- **Unit** (pure domain only, zero I/O): Case A OIL and GAS demand vectors; Case B back-out with `old_SCOP 2.8`; the §8 worked-example vector — **exact** `hp_electricity_kwh ≈ 4,769 kWh` and **heating bucket ≈ €77/mo** (overlap 0.30 +battery), with the HP-rung Δ gross ≈ €107/mo asserted **only** when the ~€30/mo extra L1/L2 PV self-consumption is credited there (DD-1, F03 §0) — illustrative ±15 %, not a hard €107; area-method fallback by Baujahr; overlap 0.15 vs 0.30; `kfw_case` flag for A vs B; modern-HP ⇒ Δ 0.
- **Integration / contract**: assert the value lands in `breakdown.heating_eur_month` and that `annual_consumption_kwh` passed to L1/L2 reflects the HP lift (engine-level, against the frozen F02 contract shapes).
- **Demo-safety**: prices injected from a seeded `PricingContext` (offline); `?fixture` golden payload reproduces the §8 numbers; no live fuel-price call in the engine.

## 8. Dependencies & interfaces

- **Upstream (needs):** F05 (normalised intake + baseline `current_monthly_spend`, existing-equipment folding, km-based mobility), and a `PricingContext` (built by F12 from `price_catalog`, §12) for oil/gas/retail prices. F03 supplies the §5–§8 test vectors.
- **Downstream (feeds):** F10 (marginal/optimiser — Layer 3 Δ on the running state) and F11 (financing — consumes `kfw_case` flag + capex for the KfW 458 grant and annuity).
- **Mock until ready:** consumers mock Layer 3 with a fixture pair (Case A: hp_elec **4,769 kWh** exact, heating bucket **≈ €77/mo** illustrative — see DD-1 for whether the ~€30 PV uplift sits here or in L1/L2; Case B: efficiency-delta example) from the frozen contract.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Old-HP upgrade over-sold | Case B saving = efficiency delta only, **no Klima-bonus** for HP→HP (§5.3/§6.5); optimiser (F10) drops it if net-negative — §15. |
| Heat demand wrong (skews number) | Prefer actual-fuel-spend method; area method only as flagged fallback; SCOP/η/W-per-m² cited to §10. |
| Overlap over-credited in winter | `overlap` capped at 0.15/0.30 (winter-weak); HP value still mostly from displacing fossil, not PV self-use. |
| **PV→HP self-consumption double-counted (DD-1)** | The HP load's PV self-consumption is credited in **one** place only (F03 §0): under the recommended model L1/L2 carry the ~€30/mo uplift and the heating bucket prices **HP grid electricity** (no separate `solar_covered` credit here). Heating bucket pinned ≈ €77/mo; the €107 HP-rung figure is illustrative (±15 %) and includes the L1/L2 lift, not a second heating-bucket credit. |
| Hard-coded fuel prices drift | All prices injected via `PricingContext` from `price_catalog` (§12); none imported in the engine — §15. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (incl. the §8 worked-example vector: `hp_electricity_kwh ≈ 4,769` exact; heating bucket ≈ €77/mo illustrative per DD-1).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored (reads only; value flows via `breakdown.heating_eur_month`); no payload drift.
- [ ] No secret added to the frontend bundle; no hard-coded price (reads `price_catalog` via `PricingContext`).
- [ ] Every figure traces to a §10/§12 source or a labelled assumption (no invented precision).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] The demo happy-path still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §5.3, §3.2, §6.3, §6.5, §7, §10, §12
- `specs/api/openapi.yaml` · `specs/domain/savings-engine.spec.md` (§8 vectors via F03)
