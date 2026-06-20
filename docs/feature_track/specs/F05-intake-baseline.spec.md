---
id: F05
title: Intake normalisation & baseline
epic: E1 Domain Core
owner: Lukas
reviewers: [Lukas]
priority: P1
mvp: true
status: Ready
branch: feat/F05-intake-baseline
depends_on: [F03]
contract_impact: reads
estimate_h: 2
---

# F05 — Intake normalisation & baseline

> **North-Star link:** produces `current_monthly_spend` — the **first term** of
> `monthly_saving = current_monthly_spend − (loan_installment + new_energy_cost)` — and the physical
> baselines (kWh/yr, heat demand, km/yr) every layer subtracts its savings from. Get this wrong and
> every headline number is wrong.

## 1. Intent (what & why)

Turn the raw intake (form or LLM) into the engine's internal, fully-physical household model:
convert mobility €→**km**, reconstruct annual electricity / heat / mobility quantities, fold in
existing equipment so capex later lands only on the *delta* (no double-count), compute
`current_monthly_spend`, and emit a **labelled assumption** for every derived or defaulted field.
This is the deterministic pure-domain front door to Layers 1–4 (§3.1–§3.4); it does **zero I/O** and
imports no price (prices arrive via `PricingContext`, §12).

## 2. Scope

**In scope**
- €→km mobility conversion for all `CarType` (km direct; or back out from €/fuel for PETROL/DIESEL;
  or from €/public-charge for EV) — the §3.3 algorithm verbatim.
- Reconstruct physical baselines: `annual_consumption_kwh` (base electricity), `heat_demand` proxy
  inputs, `km_year`.
- Existing-equipment folding (§3.2): `existing_pv_kwp`, `existing_battery_kwh`,
  `existing_heatpump_year`, `existing_ev`, `existing_ev_charger` → counted toward starting state;
  flagged so downstream layers cost capex on the delta only.
- `current_monthly_spend` = sum of electricity + heating + mobility €/mo from intake.
- A `list[Assumption]` (label, value, source/fallback ref) for every derived/defaulted field (§3.4).

**Out of scope** (explicitly, to prevent creep)
- Layer savings math (sizing, yield, SCOP, arbitrage) → F06–F09.
- Fetching prices / PVGIS / SMARD / grid fees → that is the Resolver + adapters (F12–F14).
- Form/Zod validation and conversational-LLM parsing → frontend intake (F19); this consumes an
  already-validated DTO shaped by the frozen contract (F02).
- Site-Check feasibility flags (roof_ok, parking, Denkmal) → F15.

## 3. Functional requirements

| # | Requirement | Source (§) |
|---|-------------|------------|
| R1 | If `mobility.km_month` is given, `km_year = km_month × 12` for **any** kind. | §3.3 |
| R2 | If only `mobility.eur_month` given and kind ∈ {PETROL, DIESEL}: derive km via fuel litres. | §3.3 |
| R3 | If only `mobility.eur_month` given and kind == EV: derive km via `public_charge_per_kwh`. | §3.3 |
| R4 | kind == NONE ⇒ `km_year = 0` (no mobility baseline, Layer 4 later Δ=0). | §3.2 |
| R5 | Produce `annual_consumption_kwh` (base electricity, before HP/EV load) from electricity spend at retail price. | §3.1, §5.1 |
| R6 | Fold existing equipment into starting state; mark each owned item so capex applies to the delta only (no double-count). | §3.2 |
| R7 | `current_monthly_spend = electricity_eur_month + heating.eur_month + mobility_eur_month`. | §8 (baseline def) |
| R8 | Every derived/defaulted field emits a labelled `Assumption`; user overrides replace the default and are flagged as `source="user"`. | §3.4 |
| R9 | Pure & deterministic: same input DTO → identical output; no network, clock, filesystem, or RNG. | §2, §1 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> No hard-coded prices. Every €/unit (`petrol_per_litre`, `diesel_per_litre`, `public_charge_per_kwh`,
> `retail_per_kwh`) is read from `PricingContext` built from `price_catalog` (§12). This table holds
> the **physical** constants and the conversion formula only.

| Quantity / call | Value | Official source | Fallback | Used in |
|---|---|---|---|---|
| Petrol consumption | 7.0 L/100 km | class default / ADAC (§10) | const 7.0 | §3.3 €→km |
| Diesel consumption | 6.0 L/100 km | class default / ADAC (§10) | const 6.0 | §3.3 €→km |
| EV consumption | 18 kWh/100 km | class default (§10) | const 18 | §3.3 €→km, base load |
| `petrol_per_litre` | €1.85/L | Destatis/ADAC → `price_catalog` (§12) | seed €1.85 | §3.3 PETROL branch |
| `diesel_per_litre` | €1.75/L | Destatis/ADAC → `price_catalog` (§12) | seed €1.75 | §3.3 DIESEL branch |
| `public_charge_per_kwh` | €0.45/kWh | CPO avg → `price_catalog` (§12) | seed €0.45 | §3.3 EV branch |
| `retail_per_kwh` | €0.37/kWh | Destatis/BNetzA → `price_catalog` (§12) | seed €0.37 | base-load reconstruction |

§3.3 mobility €→km algorithm, copied verbatim so the implementer codes against one definition:
```
# canonical internal quantity = km_year. If the user gives km, use it directly (any kind).
if mobility.km_month given:
    km_year = mobility.km_month × 12
elif mobility.eur_month given:
    if kind ∈ {PETROL, DIESEL}:                       # € is fuel spend
        litres_year = eur_month × 12 / fuel_price_per_litre[kind]
        km_year     = litres_year / consumption_l_per_100km[kind] × 100
    elif kind == EV:                                  # € is current charging spend (public price)
        kwh_year = eur_month × 12 / public_charge_per_kwh
        km_year  = kwh_year / ev_consumption_kwh_per_100km × 100
```

Existing-equipment folding (§3.2): `existing_pv_kwp` / `existing_battery_kwh` count toward installed
state (production/arbitrage later computed on **total**, capex on the **delta**); `existing_heatpump_year`
null ⇒ fossil case; `existing_ev`/`existing_ev_charger` set the mobility baseline kind (fuel vs charging
cost) and Layer-4 case. The current bill already reflects owned self-consumption → downstream credits
only the *incremental* (§3.2, enforced in F06/F07).

Base-load reconstruction: `annual_consumption_kwh = electricity_eur_month × 12 / retail_per_kwh`
(worked example: €95/mo ÷ €0.37 × 12 ≈ **3,081 kWh/yr**, §8).

## 5. Contract surface  *(contract_impact = reads)*

- Reads `Household` from `specs/api/openapi.yaml` (F02): `address{street,house_no,city}`, `plz`,
  `floor_area_m2`, `building_year`, `occupants`, electricity spend, `heating{fuel,eur_month}`,
  `mobility{kind, km_month|eur_month}`, and the existing-equipment fields
  (`existing_pv_kwp`, `existing_battery_kwh`, `existing_heatpump_year`, `existing_ev`,
  `existing_ev_charger`).
- New/changed schema objects: none (does not extend the contract; consumes it).
- Backwards-compatible? yes — read-only.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (km direct)** — Given `mobility={kind:PETROL, km_month:1233}`, when normalised, then
  `km_year == 14796` (≈ the §8 14,800 km figure).
- [ ] **AC2 (€→km petrol)** — Given `mobility={kind:PETROL, eur_month:160}`, petrol €1.85/L @ 7.0
  L/100 km, when normalised, then `litres_year == 160×12/1.85 ≈ 1037.8 L` and
  `km_year == 1037.8/7.0×100 ≈ 14826 km` (±1 %).
- [ ] **AC3 (€→km EV)** — Given `mobility={kind:EV, eur_month:100}`, public €0.45/kWh, 18 kWh/100 km,
  when normalised, then `kwh_year == 100×12/0.45 ≈ 2667 kWh` and `km_year ≈ 14815 km` (±1 %).
- [ ] **AC4 (base load)** — Given electricity €95/mo, retail €0.37/kWh, when normalised, then
  `annual_consumption_kwh ≈ 3081 kWh` (±1) — the §8 base-load vector.
- [ ] **AC5 (baseline spend)** — Given €95 elec + €180 oil + €160 petrol, then
  `current_monthly_spend == 435.0` (€/mo, the §8 baseline).
- [ ] **AC6 (existing PV no double-count)** — Given `existing_pv_kwp=5`, when normalised, then state
  carries `existing_pv_kwp=5` and a flag that Layer 1 must credit only incremental yield (capex on
  the delta), and the reconstructed base load is **unchanged** (existing self-consumption already in
  the bill).
- [ ] **AC7 (honesty/edge — NONE + assumptions)** — Given `mobility={kind:NONE}` and no
  `floor_area` override, then `km_year == 0` **and** every defaulted field (consumptions, fuel prices,
  retail price) appears in the returned `assumptions[]` with a label and source/fallback ref; a
  user-supplied override replaces the default and is flagged `source="user"`.

## 7. Test plan

- **Unit** (pure, zero I/O): all of AC1–AC7 as table-driven vectors; the §8 baseline
  (€435/mo, 3,081 kWh, 14,800 km) as a named golden fixture; property test: km direct path is
  independent of any price; determinism (same DTO twice → equal dataclass).
- **Integration / contract**: a fixture `Household` decoded from the frozen `openapi.yaml` schema
  normalises without KeyError; field names match the contract exactly.
- **Demo-safety**: with `PricingContext` built from seeded `price_catalog` constants (no live call),
  the golden fixture reproduces the §8 baseline exactly.

## 8. Dependencies & interfaces

- **Upstream (needs):** F03 (domain spec — dataclasses, `Assumption` type, `PricingContext` shape);
  the validated `Household` DTO (shape from F02). Consumes prices via injected `PricingContext`.
- **Downstream (feeds):** F06 (base load + existing-PV state), F07 (existing-battery state),
  F08 (heating baseline + `existing_heatpump_year`), F09 (`km_year` + EV/charger flags),
  F10/F11 (`current_monthly_spend`).
- **Mock until ready:** a blocked consumer mocks a `NormalisedHousehold` fixture matching the §8
  worked example.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Existing equipment double-counted in baseline | capex on delta only; base load left untouched for owned PV (§3.2, §15) — asserted in AC6. |
| €→km conversion drifts from spec | copy §3.3 verbatim; lock AC2/AC3 numeric vectors. |
| A defaulted field silently hides uncertainty | R8 forces a labelled `Assumption` per derived field; AC7 asserts presence. |
| Hidden price import breaks purity | prices only via `PricingContext`; unit tests run with zero network and a stub context (§12). |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated unit tests.
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored: reads `Household` fields as frozen in `openapi.yaml`; no payload drift.
- [ ] No secret in any bundle; no hard-coded price (every €/unit from `PricingContext`/`price_catalog`).
- [ ] Every figure traces to a §10 source or a labelled assumption (no invented precision).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] Demo happy-path still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §3.1, §3.2, §3.3, §3.4, §8, §10, §12
- `specs/api/openapi.yaml` · `specs/domain/savings-engine.spec.md` (F03)
